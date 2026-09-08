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
    """Reject bad/time-disordered bars; classify closure by actual TF boundary."""
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
        self.server_offset_seconds = server_offset_seconds
        self.lock = threading.RLock()
        self.action_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.refresh_event = threading.Event()
        self.executor = executor
        self.future = None
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
        tick_time = tick.time - self.server_offset_seconds
        if tick_time > time.time() + 5:
            raise RuntimeError("MT5_CLOCK_OFFSET_MISMATCH: revise --server-utc-offset-hours")
        age = max(0, time.time() - tick_time)
        positions = self.mt5.positions_get()
        if positions is None:
            raise RuntimeError("MT5_POSITIONS_UNAVAILABLE")
        with self.lock:
            self.state["tick"] = {"bid": tick.bid, "ask": tick.ask, "time": tick_time,
                                  "time_msc": tick.time_msc - self.server_offset_seconds * 1000, "digits": info.digits,
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
                                         "server_utc_offset_hours": self.server_offset_seconds / 3600}
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
                self.event("ENGINE_UPDATED", f'{result["duration_ms"]} ms')
            except Exception as exc:
                with self.lock:
                    self.state["engine"] = {"status": "ERROR", "snapshot": None, "error": str(exc)}
                    self.state["engine_version"] += 1
                self.event("ENGINE_ERROR", exc)
            self.future = None
        with self.lock:
            closed = self.closed_bars
            signature = self.bars_signature
        if not closed or signature is None:
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
        self.future = self.executor.submit(compute_snapshot, closed, self.symbol, decision)
        self.engine_signature = signature
        with self.lock:
            self.state["engine"]["status"] = "RUNNING"
            self.state["engine"]["started_at"] = utc_now()
            self.state["engine"]["error"] = None

    def action(self, action):
        if action not in {"analyze", "arm", "disarm", "close-cycle"}:
            raise ValueError("UNKNOWN_ACTION")
        if action == "analyze":
            self.refresh_event.set()
            return {"ok": True, "action": action, "message": "Análisis en segundo plano solicitado"}
        if self.service is None:
            raise RuntimeError("BOT_UNAVAILABLE")
        with self.action_lock:
            status = self.service.status()
            if action in {"arm", "close-cycle"} and not status.get("execution_enabled"):
                raise RuntimeError("EXECUTION_DISABLED")
            # Arming is explicit human authorization. Snapshot and stochastic
            # checks remain in tick(), immediately before any OPEN action.
            method = {"arm": "arm", "disarm": "disarm", "close-cycle": "close_cycle"}[action]
            result = getattr(self.service, method)()
        with self.lock:
            self.state["bot"] = {**self.state["bot"], **result}
        self.event("BOT_ACTION", action)
        return {"ok": True, "action": action, **result}
