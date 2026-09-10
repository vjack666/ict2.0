"""Local coordinator for the mechanical MT5 bot.

The intelligent system is a read-only provider.  Absence of a fresh,
confirmed probability snapshot fails closed: it produces a dashboard status
but can never create an order.
"""
from __future__ import annotations

import json
import math
import traceback
from dataclasses import asdict
from datetime import datetime, time, timezone
from pathlib import Path
from threading import Event, RLock, Thread, current_thread
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from mechanical_bot.blackbox import BlackBoxJournal, BlackBoxWriteError, canonical_hash
from mechanical_bot.core import BotConfig, BotState, Cycle, MechanicalBot, Snapshot, SnapshotRejected, stochastic_14_3_3
from mechanical_bot.mt5_adapter import MT5Adapter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "runtime" / "mechanical_bot" / "latest_snapshot.json"
DEFAULT_STATE = ROOT / ".hermes-state" / "mechanical_bot_state.json"
DEFAULT_LOG = ROOT / ".hermes-state" / "mechanical_bot_events.jsonl"
DEFAULT_BLACKBOX = ROOT / ".hermes-state" / "mechanical_bot_blackbox.jsonl"


class MechanicalBotService:
    """One local bot service. Its only side effect is through its adapter."""
    def __init__(self, config: BotConfig | None = None, *, adapter: MT5Adapter | None = None,
                 snapshot_path: Path = DEFAULT_SNAPSHOT, state_path: Path = DEFAULT_STATE, log_path: Path = DEFAULT_LOG,
                 blackbox_path: Path = DEFAULT_BLACKBOX, entry_sessions_enabled: bool = False):
        # ``enabled`` means that a human may arm this separate controller.  It
        # does not start a cycle, connect MT5, or send an order by itself.
        self.bot = MechanicalBot(config or BotConfig(enabled=True))
        self.adapter = adapter
        self.snapshot_path, self.state_path, self.log_path = snapshot_path, state_path, log_path
        self.blackbox = BlackBoxJournal(blackbox_path)
        self.entry_sessions_enabled = entry_sessions_enabled is True
        self.manual_direction: str | None = None
        if self.adapter is not None and hasattr(self.adapter, "set_blackbox"):
            self.adapter.set_blackbox(self.blackbox)
        self._runner: Thread | None = None
        self._runner_stop = Event()
        self._runner_lock = RLock()
        # This lock covers the state machine and its broker action as one
        # transaction.  RLock permits status/persistence calls while holding it.
        self._state_lock = RLock()
        self._runner_interval_seconds = 15.0
        self._restore_state()

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            account: dict[str, Any] | None = None
            if self.adapter is not None:
                try:
                    info = self.adapter.account_status()
                    account = {"login": info.login, "server": info.server, "balance": info.balance, "equity": info.equity,
                               "environment": "DEMO" if info.is_demo else "REAL", "real_account_warning": not info.is_demo}
                except Exception as exc:
                    account = {"status": "UNAVAILABLE", "error": str(exc)}
            cycle = None if self.bot.cycle is None else _json_safe(asdict(self.bot.cycle))
            return {"state": self.bot.state.value, "symbol": self.bot.config.symbol, "execution_enabled": bool(getattr(self.adapter, "execution_enabled", False)),
                    "account": account, "cycle": cycle, "m5_m1": "DIAGNOSTIC_ONLY_NO_VETO",
                    "session_schedule": self._session_schedule(), "demo_wait_enabled": bool(getattr(self, "demo_wait_enabled", False)),
                    "manual_direction": self.manual_direction,
                    "black_box": self.blackbox.summary()}

    def analyze(self) -> dict[str, Any]:
        raw, snapshot_error = self._read_snapshot_with_status()
        snapshot = self._snapshot_from_raw(raw)
        result = self.status()
        result["snapshot"] = {"direction": snapshot.direction, "probability": snapshot.probability, "confirmed": snapshot.confirmed,
                              "asof_time": snapshot.asof_time.isoformat()} if snapshot else None
        # These fields travel untouched from the canonical producer.  They are
        # transparent dashboard evidence; only the snapshot and M15 stochastic
        # are decision inputs for this separate mechanical controller.
        result["context"] = {
            "context_state": raw.get("context_state"),
            "zones": raw.get("zones", []),
            "bos": raw.get("bos", []),
            "m5_m1": raw.get("m5_m1", "DIAGNOSTIC_ONLY_NO_VETO"),
        } if raw else None
        stochastic = None
        stochastic_error = None
        if self.adapter is not None:
            try:
                candles = self.adapter.closed_m15_candles(self.bot.config.symbol)
                stochastic = stochastic_14_3_3(candles, self.bot.config)
            except Exception as exc:
                stochastic_error = str(exc)
            result["stochastic_m15"] = None if stochastic is None else asdict(stochastic)
        result["readiness"] = self._readiness(raw, snapshot, stochastic, datetime.now(timezone.utc),
                                               snapshot_error=snapshot_error, stochastic_error=stochastic_error)
        return result

    def _readiness(self, raw: dict[str, Any] | None, snapshot: Snapshot | None, stochastic: Any,
                   evaluated_at: datetime, *, snapshot_error: str | None = None,
                   stochastic_error: str | None = None) -> dict[str, Any]:
        """Describe the existing entry gates without changing their authority.

        This is deliberately a dashboard projection.  ``tick`` remains the
        only place that invokes the state machine and can reach the adapter.
        """
        def gate(identifier: str, label: str, passed: bool, code: str, detail: str,
                 *, observed: Any = None, required: Any = None) -> dict[str, Any]:
            item = {"id": identifier, "label": label, "passed": passed, "code": code, "detail": detail}
            if observed is not None:
                item["observed"] = _json_safe(observed)
            if required is not None:
                item["required"] = _json_safe(required)
            return item

        now = _as_utc(evaluated_at)
        execution_enabled = bool(getattr(self.adapter, "execution_enabled", False))
        execution_gate = gate(
            "execution_enabled", "Ejecución habilitada", execution_enabled,
            "PASS" if execution_enabled else "EXECUTION_DISABLED",
            "El adaptador permite el loop de MT5." if execution_enabled else "El adaptador tiene execution_enabled=false; no se puede ejecutar.",
            observed=execution_enabled, required=True,
        )

        snapshot_code, snapshot_detail = "PASS", "Snapshot canónico válido y fresco."
        age_seconds: float | None = None
        asof: datetime | None = None
        if raw is None:
            snapshot_code = snapshot_error or "SNAPSHOT_MISSING"
            snapshot_detail = ("No hay snapshot canónico disponible." if snapshot_code == "SNAPSHOT_MISSING"
                               else "El snapshot existe, pero no se puede leer como JSON canónico.")
        elif snapshot is None:
            snapshot_code, snapshot_detail = "SNAPSHOT_INVALID", "El snapshot no tiene la forma canónica requerida."
        else:
            asof = _as_utc(snapshot.asof_time)
            if snapshot.symbol != self.bot.config.symbol:
                snapshot_code, snapshot_detail = "SNAPSHOT_SYMBOL_MISMATCH", "El símbolo del snapshot no coincide con el símbolo configurado."
            else:
                age_seconds = (now - asof).total_seconds()
                max_age = self.bot.config.stale_after.total_seconds()
                if age_seconds < 0:
                    snapshot_code, snapshot_detail = "SNAPSHOT_FUTURE", "El snapshot está %.1f s en el futuro." % abs(age_seconds)
                elif age_seconds > max_age:
                    snapshot_code, snapshot_detail = "SNAPSHOT_STALE", "Antigüedad %.1f s; máximo permitido %.0f s." % (age_seconds, max_age)
                else:
                    snapshot_detail = "Snapshot válido; antigüedad %.1f s de %.0f s permitidos." % (age_seconds, max_age)
        snapshot_gate = gate(
            "snapshot", "Snapshot canónico", snapshot_code == "PASS", snapshot_code, snapshot_detail,
            observed={"symbol": None if snapshot is None else snapshot.symbol, "asof_time": None if asof is None else asof.isoformat(),
                      "age_seconds": age_seconds},
            required={"symbol": self.bot.config.symbol, "max_age_seconds": self.bot.config.stale_after.total_seconds()},
        )

        raw_direction = None if raw is None else raw.get("direction")
        direction = None
        if isinstance(raw_direction, str):
            normalized = raw_direction.upper()
            if normalized in {"BUY", "BULLISH", "LONG"}:
                direction = "BUY"
            elif normalized in {"SELL", "BEARISH", "SHORT"}:
                direction = "SELL"
        direction_gate = gate(
            "direction", "Dirección", direction in {"BUY", "SELL"},
            "PASS" if direction in {"BUY", "SELL"} else "DIRECTION_INVALID",
            "Dirección normalizada a %s." % direction if direction in {"BUY", "SELL"} else
            "Dirección observada %r; se requiere BUY o SELL." % raw_direction,
            observed=raw_direction, required=["BUY", "SELL"],
        )

        probability = None if raw is None else raw.get("probability")
        probability_valid = (isinstance(probability, (int, float)) and not isinstance(probability, bool)
                             and math.isfinite(probability) and 0.0 <= probability <= 1.0)
        probability_ok = probability_valid and probability >= self.bot.config.min_probability
        probability_code = "PASS" if probability_ok else ("PROBABILITY_BELOW_MINIMUM" if probability_valid else "PROBABILITY_INVALID")
        probability_gate = gate(
            "probability", "Probabilidad", probability_ok,
            probability_code,
            "La probabilidad alcanza el mínimo configurado." if probability_ok else
            ("Probabilidad %.1f%%; mínimo requerido %.1f%%." % (probability * 100, self.bot.config.min_probability * 100)
             if probability_valid else "Probabilidad observada %r; debe ser numérica, finita y estar entre 0 y 1." % probability),
            observed=probability, required={"min_probability": self.bot.config.min_probability},
        )

        confirmed = None if raw is None else raw.get("confirmed")
        if confirmed is not True:
            m15_passed, m15_code, m15_detail = False, "M15_CONFIRMATION_MISSING", "El snapshot no tiene confirmed=true de forma estricta."
        elif direction not in {"BUY", "SELL"}:
            m15_passed, m15_code, m15_detail = False, "M15_DIRECTION_UNAVAILABLE", "No se puede contrastar el cruce M15 sin una dirección válida."
        elif stochastic_error is not None:
            m15_passed, m15_code = False, "M15_DATA_UNAVAILABLE"
            m15_detail = "No se pudieron leer velas M15 cerradas: %s" % stochastic_error
        elif stochastic is None:
            m15_passed, m15_code, m15_detail = False, "M15_READING_MISSING", "No hay lectura estocástica M15 de velas cerradas."
        elif direction == "BUY" and stochastic.crossed_up_from_oversold(self.bot.config.oversold):
            m15_passed, m15_code, m15_detail = True, "PASS", "Cruce M15 alcista compatible desde sobreventa."
        elif direction == "SELL" and stochastic.crossed_down_from_overbought(self.bot.config.overbought):
            m15_passed, m15_code, m15_detail = True, "PASS", "Cruce M15 bajista compatible desde sobrecompra."
        else:
            m15_passed, m15_code = False, "M15_CROSS_INCOMPATIBLE"
            m15_detail = "Sin cruce %s compatible: K %.2f / D %.2f; previo K %.2f / D %.2f." % (
                direction, stochastic.k, stochastic.d, stochastic.previous_k, stochastic.previous_d)
        m15_gate = gate("m15_confirmation", "Confirmación M15", m15_passed, m15_code, m15_detail,
                        observed=None if stochastic is None else asdict(stochastic), required="confirmed=true y cruce estocástico M15 compatible")

        schedule = self._session_schedule()
        active = [item["name"] for item in schedule["sessions"] if item.get("active")]
        session_passed = not self.entry_sessions_enabled or bool(active)
        session_gate = gate(
            "session", "Sesión de entrada", session_passed,
            "PASS" if session_passed else "OUTSIDE_ENTRY_WINDOW",
            "Gate de sesión no requerido por la configuración actual." if not self.entry_sessions_enabled else
            ("Sesión activa: %s." % ", ".join(active) if active else "No hay una sesión de entrada activa."),
            observed={"enabled": self.entry_sessions_enabled, "active_sessions": active}, required="sesión activa" if self.entry_sessions_enabled else "no requerido",
        )
        gates = [execution_gate, snapshot_gate, direction_gate, probability_gate, m15_gate, session_gate]
        return {"ready": all(item["passed"] for item in gates), "scan_can_start": execution_enabled,
                "gates": gates, "evaluated_at": now.isoformat()}

    def arm(self) -> dict[str, Any]:
        with self._state_lock:
            self.bot.arm()
            self._persist_state()
            self._record("ARMED")
            if self.adapter is not None and bool(getattr(self.adapter, "execution_enabled", False)):
                self.start_runner()
            return self.status()

    def disarm(self) -> dict[str, Any]:
        # Wait for an in-flight tick before returning OFF.  This prevents a
        # delayed OPEN from appearing after an operator receives this response.
        self.stop_runner()
        with self._state_lock:
            self.bot.stop()
            self._persist_state()
            self._record("OFF")
            return self.status()

    def close_cycle(self) -> dict[str, Any]:
        with self._state_lock:
            if self.bot.cycle is None:
                return self.status()
            return self._execute("CLOSE_ALL", "manual_close")

    def manual_entry(self, direction: str) -> dict[str, Any]:
        """Select a direction and wait for its M15 stochastic confirmation."""
        with self._state_lock:
            side = str(direction).upper()
            if side not in {"BUY", "SELL"}:
                raise ValueError("direction must be BUY or SELL")
            if self.adapter is None or not bool(getattr(self.adapter, "execution_enabled", False)):
                raise RuntimeError("EXECUTION_DISABLED")
            sessions = self._session_schedule()["sessions"]
            active = {item["name"] for item in sessions if item["active"]}
            if not active:
                raise RuntimeError("OUTSIDE_ENTRY_WINDOW")
            if "LONDON" in active and side != "SELL":
                raise RuntimeError("LONDON_SELL_ONLY")
            if self.bot.state == BotState.OFF:
                raise RuntimeError("BOT_NOT_ACTIVE")
            if self.bot.cycle is not None:
                raise RuntimeError("cycle already active")
            self.manual_direction = side
            self.bot.state = BotState.WAIT_STOCHASTIC
            self._persist_state()
            self._record("MANUAL_DIRECTION_SELECTED", direction=side, reason="WAIT_M15_STOCHASTIC")
            return self.status()

    def tick(self) -> dict[str, Any]:
        """Run one bounded decision tick; callers schedule it, never a hidden loop."""
        with self._state_lock:
            if self.adapter is None:
                raise RuntimeError("MT5 adapter is not configured")
            if self.bot.state in {BotState.OFF, BotState.ERROR, BotState.CLOSING}:
                return self.status()
            raw = self._read_snapshot()
            snapshot = self._snapshot_from_raw(raw)
            candles = self.adapter.closed_m15_candles(self.bot.config.symbol)
            stochastic = stochastic_14_3_3(candles, self.bot.config)
            now = datetime.now(timezone.utc)
            correlation_id = str(uuid4())
            action = None
            abstention: str | None = None
            if self.bot.cycle is None:
                if self.entry_sessions_enabled and not any(item["active"] for item in self._session_schedule()["sessions"]):
                    self.bot.state = BotState.WAIT_SIGNAL
                    abstention = "OUTSIDE_ENTRY_WINDOW"
                elif self.manual_direction is not None:
                    side = self.manual_direction
                    allowed = ((side == "BUY" and stochastic is not None and stochastic.crossed_up_from_oversold(self.bot.config.oversold)) or
                               (side == "SELL" and stochastic is not None and stochastic.crossed_down_from_overbought(self.bot.config.overbought)))
                    if allowed:
                        account = self.adapter.account_status()
                        price = self.adapter.tick_price(self.bot.config.symbol, side)
                        action = self.bot.manual_entry(side, price, account.balance, now)
                        self.manual_direction = None
                    else:
                        self.bot.state = BotState.WAIT_STOCHASTIC
                        abstention = "WAIT_MANUAL_DIRECTION_STOCHASTIC"
                elif snapshot is None:
                    self.bot.state = BotState.WAIT_SIGNAL
                    # Arming starts the live loop immediately. Missing engine
                    # data blocks direction, but the scanner remains active.
                    abstention = "WAIT_DIRECTION"
                else:
                    account = self.adapter.account_status()
                    price = self.adapter.tick_price(self.bot.config.symbol, "BUY")
                    try:
                        action = self.bot.decide_entry(snapshot, stochastic, price, account.balance, now)
                    except SnapshotRejected as exc:
                        self.bot.state = BotState.WAIT_SIGNAL
                        abstention = f"SNAPSHOT_REJECTED:{exc}"
                    if action is None and abstention is None:
                        if stochastic is None:
                            abstention = "WAIT_STOCHASTIC_NO_READING"
                        elif self.bot.last_closed_signal_time is not None and _as_utc(snapshot.asof_time) <= _as_utc(self.bot.last_closed_signal_time):
                            abstention = "REUSED_CLOSED_SIGNAL"
                        else:
                            abstention = "WAIT_STOCHASTIC_CROSS"
            else:
                price = self.adapter.tick_price(self.bot.config.symbol, self.bot.cycle.direction)
                action = self.bot.monitor(price, self.adapter.positions())
                if action is None:
                    abstention = "MONITOR_NO_ACTION" if self.bot.state != BotState.ERROR else "OWN_POSITIONS_MISSING"
            self._record_decision(correlation_id, raw, snapshot, stochastic, action, abstention)
            if action is None:
                return self.status()
            return self._execute(action.kind, action.reason, action=action, correlation_id=correlation_id)

    def start_runner(self, interval_seconds: float = 15.0) -> None:
        """Run bounded MT5 ticks only after explicit arming and execution enablement.

        The loop waits on an event rather than busy-spinning.  It is intentionally
        owned by this service so the dashboard's Arm/Stop controls operate the
        same state machine and cannot create duplicate runners.
        """
        if self.adapter is None or not bool(getattr(self.adapter, "execution_enabled", False)):
            return
        with self._runner_lock:
            if self._runner is not None and self._runner.is_alive():
                return
            self._runner_interval_seconds = max(5.0, float(interval_seconds))
            self._runner_stop.clear()
            self._runner = Thread(target=self._run, name="mechanical-bot", daemon=True)
            self._runner.start()

    def stop_runner(self) -> None:
        self._runner_stop.set()
        with self._runner_lock:
            runner = self._runner
        if runner is not None and runner.is_alive() and runner is not current_thread():
            # MT5 calls are external I/O; never let the dashboard hang forever
            # if a terminal call stops responding during shutdown.
            runner.join(timeout=8.0)

    def _run(self) -> None:
        while not self._runner_stop.is_set():
            try:
                self.tick()
            except Exception as exc:
                with self._state_lock:
                    self.bot.state = BotState.ERROR
                    self._persist_state()
                    self._record("RUNNER_ERROR", error=str(exc), traceback=traceback.format_exc())
                return
            if self._runner_stop.wait(self._runner_interval_seconds):
                return

    def _execute(self, kind: str, reason: str, *, action: Any | None = None, correlation_id: str | None = None) -> dict[str, Any]:
        with self._state_lock:
            if self.adapter is None:
                raise RuntimeError("MT5 adapter is not configured")
            if action is None:
                from mechanical_bot.core import BotAction
                action = BotAction(kind, reason)
            try:
                if kind == "CLOSE_ALL":
                    before_close = [position for position in self.adapter.positions()
                                    if position.symbol == self.bot.config.symbol and position.magic_number == self.bot.config.magic_number]
                    if not before_close:
                        raise RuntimeError("close reconciliation failed: no matching bot positions")
                results = self.adapter.execute(action, symbol=self.bot.config.symbol, magic_number=self.bot.config.magic_number,
                                               correlation_id=correlation_id)
                if kind == "CLOSE_ALL":
                    remaining = [position for position in self.adapter.positions()
                                 if position.symbol == self.bot.config.symbol and position.magic_number == self.bot.config.magic_number]
                    if remaining:
                        raise RuntimeError("close reconciliation failed: matching bot positions remain")
            except Exception as exc:
                # An uncertain broker response must never be retried as an OPEN.
                # Preserve the cycle for audit, but require explicit reconciliation.
                self.bot.state = BotState.ERROR
                self._persist_state()
                self._record("EXECUTION_ERROR", reason=reason, correlation_id=correlation_id, error=str(exc))
                raise
            if kind == "CLOSE_ALL":
                self.bot.complete_close()
            self._persist_state()
            self._record(kind, reason=reason, results=results, correlation_id=correlation_id)
            return self.status()

    def _record_decision(self, correlation_id: str, raw: dict[str, Any] | None, snapshot: Snapshot | None,
                         stochastic: Any, action: Any, abstention: str | None) -> None:
        """Persist every tick before a potential broker request.

        Failure is intentionally terminal for this tick.  An action cannot
        reach the adapter without a durable decision record and correlation ID.
        """
        try:
            self.blackbox.record(
                "DECISION",
                correlation_id=correlation_id,
                raw_snapshot_hash=None if raw is None else canonical_hash(raw),
                raw_snapshot_hash_scope="full_canonical_json",
                snapshot=None if snapshot is None else _json_safe(asdict(snapshot)),
                stochastic=None if stochastic is None else _json_safe(asdict(stochastic)),
                state_before=self.bot.state.value,
                action=None if action is None else _json_safe(asdict(action)),
                reason=action.reason if action is not None else abstention,
                strategy=_strategy_fields(raw),
            )
        except BlackBoxWriteError as exc:
            self.bot.state = BotState.ERROR
            self._persist_state()
            raise RuntimeError("mechanical bot stopped: black-box decision persistence failed") from exc

    def _session_schedule(self, at: datetime | None = None) -> dict[str, Any]:
        """Expose London and New York 08:00--12:00 in both requested clocks."""
        guayaquil = ZoneInfo("America/Guayaquil")
        now = datetime.now(guayaquil) if at is None else _as_utc(at).astimezone(guayaquil)
        definitions = (("LONDON", ZoneInfo("Europe/London")), ("NEW_YORK", ZoneInfo("America/New_York")))
        sessions = []
        for name, zone in definitions:
            local_now = now.astimezone(zone)
            local_today = local_now.date()
            start = datetime.combine(local_today, time(8, 0), tzinfo=zone)
            end = datetime.combine(local_today, time(12, 0), tzinfo=zone)
            sessions.append({
                "name": name,
                "weekdays_only": True,
                "active": local_now.weekday() < 5 and start <= local_now < end,
                "start_local": start.isoformat(), "end_local": end.isoformat(),
                "start_guayaquil": start.astimezone(guayaquil).isoformat(), "end_guayaquil": end.astimezone(guayaquil).isoformat(),
                "start_utc": start.astimezone(timezone.utc).isoformat(), "end_utc": end.astimezone(timezone.utc).isoformat(),
            })
        return {"enabled": self.entry_sessions_enabled, "sessions": sessions}

    def _load_snapshot(self) -> Snapshot | None:
        return self._snapshot_from_raw(self._read_snapshot())

    def _read_snapshot(self) -> dict[str, Any] | None:
        return self._read_snapshot_with_status()[0]

    def _read_snapshot_with_status(self) -> tuple[dict[str, Any] | None, str | None]:
        try:
            raw = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            return (raw, None) if isinstance(raw, dict) else (None, "SNAPSHOT_INVALID")
        except FileNotFoundError:
            return None, "SNAPSHOT_MISSING"
        except (OSError, ValueError, KeyError, TypeError):
            return None, "SNAPSHOT_INVALID"

    def _snapshot_from_raw(self, raw: dict[str, Any] | None) -> Snapshot | None:
        try:
            if raw is None:
                return None
            direction, probability, confirmed, asof_time, symbol = raw["direction"], raw["probability"], raw["confirmed"], raw["asof_time"], raw["symbol"]
            if not isinstance(direction, str) or type(confirmed) is not bool or not isinstance(symbol, str) or not symbol.strip():
                return None
            if (not isinstance(probability, (int, float)) or isinstance(probability, bool)
                    or not math.isfinite(probability)):
                return None
            return Snapshot(direction, float(probability), confirmed,
                            datetime.fromisoformat(str(asof_time).replace("Z", "+00:00")), symbol)
        except (ValueError, KeyError, TypeError):
            return None

    def _record(self, event: str, **extra: Any) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        body = {"time": datetime.now(timezone.utc).isoformat(), "event": event, "status": self.status(), **extra}
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, ensure_ascii=False, default=str) + "\n")

    def _persist_state(self) -> None:
        """Atomically persist only bot state; account and snapshots stay read-only."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        cycle = None if self.bot.cycle is None else _json_safe(asdict(self.bot.cycle))
        body = {
            "schema_version": 2,
            "state": self.bot.state.value,
            "cycle": cycle,
            "last_closed_signal_time": None if self.bot.last_closed_signal_time is None else self.bot.last_closed_signal_time.isoformat(),
            # A selected manual side is durable only so a restart can make its
            # cancellation explicit.  It is never a resumable order intent.
            "manual_direction": self.manual_direction,
        }
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    def _restore_state(self) -> None:
        """Recover a saved cycle without automatically arming or executing it.

        A manual selection has no restart authority.  Persisting it lets the
        next process produce an auditable cancellation rather than presenting
        a misleading WAIT_STOCHASTIC state or silently reopening an order.
        """
        try:
            body = json.loads(self.state_path.read_text(encoding="utf-8"))
            cycle_raw = body.get("cycle")
            if cycle_raw:
                self.bot.cycle = Cycle(
                    direction=str(cycle_raw["direction"]),
                    initial_price=float(cycle_raw["initial_price"]),
                    balance_at_start=float(cycle_raw["balance_at_start"]),
                    signal_time=datetime.fromisoformat(str(cycle_raw["signal_time"]).replace("Z", "+00:00")),
                    entries=int(cycle_raw.get("entries", 1)),
                )
            closed = body.get("last_closed_signal_time")
            if closed:
                self.bot.last_closed_signal_time = datetime.fromisoformat(str(closed).replace("Z", "+00:00"))
            # A process restart may not silently resume an armed/entry state.
            # It requires the human to arm it again, then the normal tick sees
            # the restored cycle and only manages its own magic-number trades.
            self.bot.state = BotState.OFF
            pending_direction = body.get("manual_direction")
            if pending_direction in {"BUY", "SELL"}:
                self.manual_direction = None
                self.blackbox.record("CANCELLED_BY_RESTART", direction=pending_direction,
                                     reason="MANUAL_DIRECTION_NOT_RESUMABLE")
                self._persist_state()
                self._record("CANCELLED_BY_RESTART", direction=pending_direction,
                             reason="MANUAL_DIRECTION_NOT_RESUMABLE")
        except (OSError, ValueError, KeyError, TypeError):
            return


def _strategy_fields(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize strategy evidence for black-box queries without fabricating it."""
    if not isinstance(raw, dict):
        return {"phase": None, "poi": None, "bos_choch": None, "m15_structure": None, "session": None}
    return {"phase": raw.get("wyckoff_phase", raw.get("phase")),
            "poi": raw.get("poi", raw.get("zones")),
            "bos_choch": raw.get("bos", raw.get("choch")),
            "m15_structure": raw.get("m15_structure", raw.get("structure")),
            "session": raw.get("session")}


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


__all__ = ["MechanicalBotService"]
