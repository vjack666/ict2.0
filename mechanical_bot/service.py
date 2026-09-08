"""Local coordinator for the mechanical MT5 bot.

The intelligent system is a read-only provider.  Absence of a fresh,
confirmed probability snapshot fails closed: it produces a dashboard status
but can never create an order.
"""
from __future__ import annotations

import json
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
                    "black_box": self.blackbox.summary()}

    def analyze(self) -> dict[str, Any]:
        raw = self._read_snapshot()
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
        if self.adapter is not None:
            candles = self.adapter.closed_m15_candles(self.bot.config.symbol)
            reading = stochastic_14_3_3(candles, self.bot.config)
            result["stochastic_m15"] = None if reading is None else asdict(reading)
        return result

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
                elif snapshot is None:
                    self.bot.state = BotState.WAIT_SIGNAL
                    abstention = "WAIT_SNAPSHOT"
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
            runner.join()

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
            )
        except BlackBoxWriteError as exc:
            self.bot.state = BotState.ERROR
            self._persist_state()
            raise RuntimeError("mechanical bot stopped: black-box decision persistence failed") from exc

    def _session_schedule(self) -> dict[str, Any]:
        """Expose London and New York 08:00--12:00 in both requested clocks."""
        guayaquil = ZoneInfo("America/Guayaquil")
        now = datetime.now(guayaquil)
        definitions = (("LONDON", ZoneInfo("Europe/London")), ("NEW_YORK", ZoneInfo("America/New_York")))
        sessions = []
        for name, zone in definitions:
            local_today = now.astimezone(zone).date()
            start = datetime.combine(local_today, time(8, 0), tzinfo=zone)
            end = datetime.combine(local_today, time(12, 0), tzinfo=zone)
            sessions.append({
                "name": name,
                "weekdays_only": True,
                "active": now.weekday() < 5 and start <= now.astimezone(zone) < end,
                "start_local": start.isoformat(), "end_local": end.isoformat(),
                "start_guayaquil": start.astimezone(guayaquil).isoformat(), "end_guayaquil": end.astimezone(guayaquil).isoformat(),
                "start_utc": start.astimezone(timezone.utc).isoformat(), "end_utc": end.astimezone(timezone.utc).isoformat(),
            })
        return {"enabled": self.entry_sessions_enabled, "sessions": sessions}

    def _load_snapshot(self) -> Snapshot | None:
        return self._snapshot_from_raw(self._read_snapshot())

    def _read_snapshot(self) -> dict[str, Any] | None:
        try:
            raw = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _snapshot_from_raw(self, raw: dict[str, Any] | None) -> Snapshot | None:
        try:
            if raw is None:
                return None
            direction, probability, confirmed, asof_time, symbol = raw["direction"], raw["probability"], raw["confirmed"], raw["asof_time"], raw["symbol"]
            if not isinstance(direction, str) or type(confirmed) is not bool or not isinstance(symbol, str) or not symbol.strip():
                return None
            if not isinstance(probability, (int, float)) or isinstance(probability, bool):
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
            "schema_version": 1,
            "state": self.bot.state.value,
            "cycle": cycle,
            "last_closed_signal_time": None if self.bot.last_closed_signal_time is None else self.bot.last_closed_signal_time.isoformat(),
        }
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    def _restore_state(self) -> None:
        """Recover a saved cycle without automatically arming or executing it."""
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
        except (OSError, ValueError, KeyError, TypeError):
            return


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


__all__ = ["MechanicalBotService"]
