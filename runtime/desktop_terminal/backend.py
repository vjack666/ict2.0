"""Bounded MT5 cache and off-process canonical engine for the desktop terminal."""
from __future__ import annotations

import json
import hashlib
import math
import secrets
import threading
import time
import subprocess
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from runtime.desktop_terminal.snapshot_health import canonical_health
from mechanical_bot.blackbox import BlackBoxWriteError
from concurrent.futures.process import BrokenProcessPool

ROOT = Path(__file__).resolve().parents[2]
TF_SECONDS = {"D1": 86400, "H4": 14400, "H1": 3600, "M15": 900, "M5": 300, "M1": 60}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def compute_snapshot(candles, symbol, decision_time):
    """Only closed-bar payloads cross the process boundary into the engine."""
    import pandas as pd
    from engine.mt5_operational_snapshot import build_mt5_operational_snapshot
    frames = {}
    for tf, rows in candles.items():
        frame = pd.DataFrame(rows)
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frames[tf] = frame
    started = time.perf_counter()
    hashes = {tf: hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest() for tf, rows in candles.items()}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
    snapshot = build_mt5_operational_snapshot(frames, decision_time, symbol=symbol,
                                            source_hashes=hashes, generator_commit=commit)
    snapshot["transport"] = {"kind": "MT5_IN_MEMORY_CLOSED_BARS", "hash_semantics": "normalized_ohlcv_json",
                              "historical_certification": False}
    return {"snapshot": snapshot, "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "updated_at": utc_now()}


def normalize_rates(rates, tf, now, server_offset_seconds=0):
    """Reject bad/time-disordered UTC-epoch bars and classify their closure."""
    if server_offset_seconds != 0:
        raise ValueError("MT5_EPOCH_OFFSET_UNSUPPORTED")
    if rates is None or len(rates) == 0:
        raise ValueError(f"NO_RATES:{tf}")
    closed, opened, previous = [], None, 0
    for row in rates:
        stamp = int(row["time"]) - server_offset_seconds
        values = {key: float(row[key]) for key in ("open", "high", "low", "close")}
        if stamp <= previous or stamp > now or not all(math.isfinite(v) and v > 0 for v in values.values()):
            raise ValueError(f"INVALID_BAR:{tf}")
        if values["low"] > min(values["open"], values["close"]) or values["high"] < max(values["open"], values["close"]):
            raise ValueError(f"INVALID_OHLC:{tf}")
        bar = {"time": stamp, **values, "tick_volume": int(row["tick_volume"])}
        previous = stamp
        if stamp + TF_SECONDS[tf] <= now:
            closed.append(bar)
        else:
            opened = bar
    if not closed:
        raise ValueError(f"NO_CLOSED_BARS:{tf}")
    return closed[-400:], opened


class LockedMT5:
    """Serialize native terminal calls shared by reader and mechanical adapter."""
    def __init__(self, module):
        self.module, self.lock = module, threading.RLock()

    def __getattr__(self, name):
        value = getattr(self.module, name)
        if not callable(value):
            return value
        def invoke(*args, **kwargs):
            with self.lock:
                return value(*args, **kwargs)
        return invoke


class TerminalRuntime:
    def __init__(self, mt5=None, service=None, symbol="EURUSD", executor=None, server_offset_seconds=0):
        self.mt5, self.service, self.symbol = mt5, service, symbol
        self.server_offset_seconds = int(server_offset_seconds)
        self.lock = threading.RLock()
        self.action_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.refresh_event = threading.Event()
        self.executor = executor
        self.future = None
        self.engine_failures = 0
        self.engine_retry_at = 0.0
        self.engine_signature = None
        self.bars_signature = None
        self.closed_bars = {}
        self.thread = None
        self.token = secrets.token_urlsafe(32)
        self.state = {"application_id": "ICT_DESKTOP_TERMINAL_V1", "source": "MT5_LOCAL", "symbol": symbol, "server_time": utc_now(),
                      "connection": {"status": "WAITING", "error": None}, "tick": None,
                      "account": None, "candles_by_tf": {}, "open_candles_by_tf": {}, "bars_version": 0,
                      "engine": {"status": "WAITING", "snapshot": None},
                      "bot": {"state": "OFF", "execution_enabled": False}, "positions": [], "events": [],
                      "metrics": {}, "csrf_token": self.token, "engine_version": 0}

    def snapshot(self, bars_version=None, engine_version=None):
        with self.lock:
            # Detach the HTTP reader from subsequent writer mutations.
            payload = {**self.state, "engine": dict(self.state["engine"])}
            payload["canonical_snapshot_health"] = canonical_health(
                self.state["engine"], self.state["connection"], self.symbol)
            if str(bars_version) == str(self.state["bars_version"]):
                payload.pop("candles_by_tf", None)
            if str(engine_version) == str(self.state["engine_version"]):
                payload["engine"].pop("snapshot", None)
            result = json.loads(json.dumps(payload, default=str, allow_nan=False))
        result["server_time"] = utc_now()
        return result

    def event(self, event, detail):
        with self.lock:
            self.state["events"] = [{"time": utc_now(), "event": event, "detail": str(detail)}, *self.state["events"]][:100]

    def _publish_bot_snapshot(self, snapshot):
        """Atomically project a certified mechanical contract, or explain why not.

        This is a POI+Stoch *observation* contract, not the legacy Phase 2B
        directional-signal contract.  It transports only closed canonical
        evidence to the separate controller.  Direction, probability and
        confirmation are never invented here.  A rejection removes a stale
        contract and writes a separate, non-executable status artifact with
        the stable cause.
        """
        path = ROOT / "runtime" / "mechanical_bot" / "latest_snapshot.json"
        status_path = path.with_name("latest_snapshot_status.json")
        path.parent.mkdir(parents=True, exist_ok=True)

        def write_atomically(destination, body):
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, allow_nan=False), encoding="utf-8")
            temporary.replace(destination)

        def reject(code, detail, *, failed_gates=None):
            path.unlink(missing_ok=True)
            status = {
                "schema_version": "MECHANICAL_BOT_SNAPSHOT_PUBLICATION_V1",
                "status": "BLOCKED",
                "code": code,
                "detail": detail,
                "failed_gates": list(failed_gates or []),
                "published_at": utc_now(),
                "publication_authorized": False,
                "can_trade": False,
                "entry_authorized": False,
                "snapshot_path": path.name,
            }
            write_atomically(status_path, status)
            return False

        if not isinstance(snapshot, dict):
            return reject("CANONICAL_SNAPSHOT_UNAVAILABLE", "No se recibió un snapshot canónico; no existe contrato mecánico que publicar.")

        if (snapshot.get("schema_version") != "MT5_OPERATIONAL_SNAPSHOT_V1"
                or snapshot.get("status") != "READY"
                or snapshot.get("policy") != "OBSERVE_ONLY_NO_ORDER"
                or snapshot.get("can_trade") is not False
                or snapshot.get("entry_authorized") is not False):
            return reject("CANONICAL_SNAPSHOT_INVALID", "El snapshot canónico no cumple el contrato observado; no se publica evidencia POI.")
        if not isinstance(snapshot.get("symbol"), str) or snapshot["symbol"] != self.symbol:
            return reject("CANONICAL_SYMBOL_INVALID", "El símbolo canónico no coincide con el símbolo configurado del bot.")
        if not isinstance(snapshot.get("decision_time"), str):
            return reject("CANONICAL_DECISION_TIME_INVALID", "Falta decision_time ISO-8601 del snapshot canónico cerrado.")
        try:
            decision_time = datetime.fromisoformat(snapshot["decision_time"].replace("Z", "+00:00"))
            decision_time = decision_time if decision_time.tzinfo else None
            if decision_time is None:
                raise ValueError("naive timestamp")
            decision_time = decision_time.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return reject("CANONICAL_DECISION_TIME_INVALID", "decision_time debe ser ISO-8601 con zona horaria.")
        now = datetime.now(timezone.utc)
        if decision_time > now:
            return reject("CANONICAL_DECISION_TIME_FUTURE", "decision_time canónico está en el futuro; no se publica evidencia POI.")
        if (now - decision_time).total_seconds() > 180:
            return reject("CANONICAL_DECISION_TIME_STALE", "decision_time canónico superó 180 segundos; no se publica evidencia POI.")
        projection = snapshot.get("object_projection")
        if not isinstance(projection, list) or not all(isinstance(item, dict) for item in projection):
            return reject("POI_OBJECT_PROJECTION_UNAVAILABLE", "No hay object_projection canónica utilizable; el controlador POI+Stoch no recibe objetos fabricados.")

        # Preserve the canonical projection byte-for-value.  The POI evaluator
        # still owns selection, price-side and closed-M15 stochastic checks.
        published = {
            "schema_version": "POI_STOCH_M15_OBSERVATION_SNAPSHOT_V1",
            "symbol": snapshot["symbol"],
            "asof_time": snapshot["decision_time"],
            "object_projection": projection,
            "source_schema_version": snapshot["schema_version"],
            "source_snapshot_status": snapshot["status"],
            "publication_authorized": False,
            "can_trade": False,
            "entry_authorized": False,
        }
        write_atomically(path, published)
        write_atomically(status_path, {
            "schema_version": "MECHANICAL_BOT_SNAPSHOT_PUBLICATION_V1",
            "status": "PUBLISHED",
            "code": "POI_STOCH_OBSERVATION_PUBLISHED",
            "detail": "Evidencia POI canónica publicada; el bot conserva los gates de frescura, sesión, can_trade y estocástico M15.",
            "failed_gates": [],
            "published_at": utc_now(),
            "publication_authorized": False,
            "can_trade": False,
            "entry_authorized": False,
            "snapshot_path": path.name,
        })
        return True

    def start(self):
        if self.thread is not None:
            return
        if self.executor is None:
            self.executor = ProcessPoolExecutor(max_workers=1)
        self.thread = threading.Thread(target=self._run, name="ict-price-cache", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
        if self.service:
            self.service.stop_runner()
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def _run(self):
        next_bars, next_bot = 0.0, 0.0
        while not self.stop_event.is_set():
            started = time.perf_counter()
            try:
                self.read_tick()
                if time.monotonic() >= next_bars:
                    self.read_bars()
                    next_bars = time.monotonic() + 5
                if time.monotonic() >= next_bot:
                    self.read_bot()
                    next_bot = time.monotonic() + 5
                self.poll_engine()
            except Exception as exc:
                with self.lock:
                    old_error = self.state["connection"].get("error")
                    self.state["connection"] = {"status": "ERROR", "error": str(exc), "updated_at": utc_now()}
                    self.state["engine"]["status"] = "ERROR"
                    self.state["engine"]["error"] = "MT5 feed unavailable; prior snapshot is historical"
                    self.engine_signature = None
                if old_error != str(exc):
                    self.event("FEED_ERROR", exc)
            with self.lock:
                self.state["metrics"]["reader_ms"] = round((time.perf_counter() - started) * 1000, 2)
            self.stop_event.wait(max(.05, 1 - (time.perf_counter() - started)))

    def read_tick(self):
        if self.mt5 is None:
            raise RuntimeError("MT5_UNAVAILABLE")
        tick = self.mt5.symbol_info_tick(self.symbol)
        info = self.mt5.symbol_info(self.symbol)
        account = self.mt5.account_info()
        if tick is None or info is None or account is None:
            raise RuntimeError("MT5_TICK_OR_ACCOUNT_UNAVAILABLE")
        if not all(math.isfinite(float(v)) and v > 0 for v in (tick.bid, tick.ask)):
            raise RuntimeError("INVALID_TICK")
        tick_time = tick.time
        if tick_time > time.time() + 5:
            raise RuntimeError("MT5_CLOCK_EPOCH_MISMATCH: MT5 epoch is unexpectedly in the future")
        age = max(0, time.time() - tick_time)
        positions = self.mt5.positions_get()
        if positions is None:
            raise RuntimeError("MT5_POSITIONS_UNAVAILABLE")
        with self.lock:
            self.state["tick"] = {"bid": tick.bid, "ask": tick.ask, "time": tick_time,
                                  "time_msc": tick.time_msc, "digits": info.digits,
                                  "spread_points": round((tick.ask - tick.bid) / info.point, 2), "age_seconds": round(age, 1)}
            self.state["account"] = {"login": account.login, "server": account.server,
                                     "balance": account.balance, "equity": account.equity,
                                     "environment": "DEMO" if account.trade_mode == 0 else "REAL"}
            self.state["positions"] = [{"ticket": p.ticket, "symbol": p.symbol, "magic": p.magic,
                                        "direction": "BUY" if p.type == 0 else "SELL", "volume": p.volume,
                                        "price_open": p.price_open, "price_current": p.price_current,
                                        "profit": p.profit} for p in positions]
            self.state["connection"] = {"status": "READY" if age <= 30 else "STALE", "error": None,
                                         "updated_at": utc_now(), "tick_age_seconds": round(age, 1),
                                         "server_utc_offset_hours": 0.0}
            for tf, opened in self.state["open_candles_by_tf"].items():
                if opened and opened["time"] <= tick_time < opened["time"] + TF_SECONDS[tf]:
                    self.state["open_candles_by_tf"][tf] = {**opened, "close": tick.bid,
                        "high": max(opened["high"], tick.bid), "low": min(opened["low"], tick.bid)}

    def read_bars(self):
        now = time.time()
        closed, opened = {}, {}
        for tf in TF_SECONDS:
            code = getattr(self.mt5, f"TIMEFRAME_{tf}")
            rates = self.mt5.copy_rates_from_pos(self.symbol, code, 0, 401)
            closed[tf], opened[tf] = normalize_rates(rates, tf, now, self.server_offset_seconds)
        signature = tuple((tf, json.dumps(rows[-2:], sort_keys=True)) for tf, rows in closed.items())
        with self.lock:
            self.closed_bars = closed
            self.state["candles_by_tf"] = closed
            self.state["open_candles_by_tf"] = opened
            if signature != self.bars_signature:
                self.state["bars_version"] += 1
            self.bars_signature = signature

    def read_bot(self):
        if self.service:
            with self.action_lock:
                bot = self.service.analyze()
            with self.lock:
                canonical = self.state["engine"].get("snapshot")
            if isinstance(canonical, dict) and isinstance(canonical.get("mechanical_signal_assessment"), dict):
                bot["signal_assessment"] = canonical["mechanical_signal_assessment"]
            bot["snapshot_status"] = "AVAILABLE" if bot.get("snapshot") else "WAIT_SNAPSHOT"
            with self.lock:
                self.state["bot"] = bot

    def poll_engine(self):
        if self.future is not None:
            if not self.future.done():
                return
            try:
                result = self.future.result()
                with self.lock:
                    self.state["engine"] = {"status": result["snapshot"]["status"], **result}
                    self.state["engine_version"] += 1
                self._publish_bot_snapshot(result.get("snapshot"))
                assessment = result.get("snapshot", {}).get("mechanical_signal_assessment")
                if self.service is not None and isinstance(assessment, dict):
                    try:
                        self.service.record_signal_assessment(assessment, result["snapshot"])
                    except BlackBoxWriteError as exc:
                        self.event("SIGNAL_ASSESSMENT_AUDIT_ERROR", str(exc))
                self.engine_failures = 0
                self.engine_retry_at = 0.0
                self.event("ENGINE_UPDATED", f'{result["duration_ms"]} ms')
            except Exception as exc:
                self._engine_failed(exc)
            self.future = None
        with self.lock:
            closed = self.closed_bars
            signature = self.bars_signature
        if not closed or signature is None:
            return
        if self.state["connection"].get("status") != "READY":
            return
        if time.monotonic() < self.engine_retry_at:
            return
        stale = [tf for tf, rows in closed.items()
                 if time.time() - (rows[-1]["time"] + TF_SECONDS[tf]) >
                 (4 * 86400 if tf == "D1" else max(180, TF_SECONDS[tf] * 2))]
        if stale:
            with self.lock:
                self.state["engine"]["status"] = "STALE"
                self.state["engine"]["error"] = f"Closed data stale: {', '.join(stale)}"
            return
        if signature == self.engine_signature and not self.refresh_event.is_set():
            return
        self.refresh_event.clear()
        decision = datetime.fromtimestamp(closed["M1"][-1]["time"] + 60, timezone.utc).isoformat()
        try:
            self.future = self.executor.submit(compute_snapshot, closed, self.symbol, decision)
        except Exception as exc:
            self._engine_failed(exc)
            return
        self.engine_signature = signature
        with self.lock:
            self.state["engine"]["status"] = "RUNNING"
            self.state["engine"]["started_at"] = utc_now()
            self.state["engine"]["error"] = None

    def _engine_failed(self, exc):
        self.engine_signature = None
        self.engine_failures += 1
        delay = min(60, 5 * 2 ** min(self.engine_failures - 1, 4))
        self.engine_retry_at = time.monotonic() + delay
        with self.lock:
            self.state["engine"] = {"status": "ERROR", "snapshot": None, "error": str(exc),
                                    "retry_after_seconds": delay}
            self.state["engine_version"] += 1
        if isinstance(exc, BrokenProcessPool):
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.executor = ProcessPoolExecutor(max_workers=1)
        self.event("ENGINE_ERROR", f"{exc}; retry in {delay}s")

    def action(self, action):
        if action not in {"analyze", "arm", "disarm", "close-cycle", "manual-buy", "manual-sell", "enable-execution"}:
            raise ValueError("UNKNOWN_ACTION")
        if action == "analyze":
            self.refresh_event.set()
            return {"ok": True, "action": action, "message": "Análisis en segundo plano solicitado"}
        if self.service is None:
            raise RuntimeError("BOT_UNAVAILABLE")
        with self.action_lock:
            status = self.service.status()
            if action == "arm" and not status.get("adapter_configured", False):
                raise RuntimeError("MT5_ADAPTER_UNAVAILABLE")
            if action == "enable-execution":
                if not status.get("execution_enabled"):
                    if not status.get("adapter_configured", False):
                        raise RuntimeError("MT5_ADAPTER_UNAVAILABLE")
                    account = status.get("account")
                    if not account or not account.get("environment") == "DEMO":
                        raise RuntimeError("EXECUTION_ENABLED_REAL_ACCOUNT_NOT_ALLOWED")
                    raw_positions = list(self.service.adapter.positions())
                    bot_positions = [
                        p for p in raw_positions
                        if p.symbol == self.service.bot.config.symbol
                        and int(p.magic_number) == int(self.service.bot.config.magic_number)
                    ]
                    if bot_positions:
                        raise RuntimeError("EXECUTION_ENABLED_BOT_POSITIONS_OPEN")
                    if raw_positions:
                        stray = {
                            "count_total": len(raw_positions),
                            "count_bot_owned": len(bot_positions),
                            "non_bot_positions": [
                                {"symbol": str(getattr(p, "symbol", "")),
                                 "magic_number": int(getattr(p, "magic_number", 0)),
                                 "side": str(getattr(p, "side", "")),
                                 "volume": float(getattr(p, "volume", 0.0)),
                                 "profit_usd": float(getattr(p, "profit_usd", 0.0))}
                                for p in raw_positions if p not in bot_positions
                            ],
                        }
                    else:
                        stray = None
                    self.service.adapter.set_execution_enabled(True)
                    result = {
                        "ok": True,
                        "action": action,
                        "execution_enabled": True,
                        "enabling_context": {
                            "account": account,
                            "positions_total": len(raw_positions),
                            "positions_bot_owned": len(bot_positions),
                            "non_bot_positions": stray,
                        },
                    }
                    self.event("EXECUTION_ENABLED", {
                        "from": False,
                        "to": True,
                        "account": account,
                        "non_bot_positions_snapshot": stray,
                    })
                else:
                    result = {"ok": True, "action": action, "execution_enabled": True}
            elif action in {"close-cycle", "manual-buy", "manual-sell"}:
                if not status.get("execution_enabled"):
                    raise RuntimeError("EXECUTION_DISABLED")
                # Arming is explicit human authorization. Snapshot and stochastic
                # checks remain in tick(), immediately before any OPEN action.
                if action in {"manual-buy", "manual-sell"}:
                    result = self.service.manual_entry(
                        "BUY" if action == "manual-buy" else "SELL"
                    )
                else:
                    result = self.service.close_cycle()
            else:
                method = {"arm": "arm", "disarm": "disarm"}[action]
                result = getattr(self.service, method)()
        with self.lock:
            self.state["bot"] = {**self.state["bot"], **result}
        self.event("BOT_ACTION", action)
        return {"ok": True, "action": action, **result}
