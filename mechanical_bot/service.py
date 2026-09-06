"""Local coordinator for the mechanical MT5 bot.

The intelligent system is a read-only provider.  Absence of a fresh,
confirmed probability snapshot fails closed: it produces a dashboard status
but can never create an order.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any

from mechanical_bot.core import BotConfig, BotState, Cycle, MechanicalBot, Snapshot, stochastic_14_3_3
from mechanical_bot.mt5_adapter import MT5Adapter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "runtime" / "mechanical_bot" / "latest_snapshot.json"
DEFAULT_STATE = ROOT / ".hermes-state" / "mechanical_bot_state.json"
DEFAULT_LOG = ROOT / ".hermes-state" / "mechanical_bot_events.jsonl"


class MechanicalBotService:
    """One local bot service. Its only side effect is through its adapter."""
    def __init__(self, config: BotConfig | None = None, *, adapter: MT5Adapter | None = None,
                 snapshot_path: Path = DEFAULT_SNAPSHOT, state_path: Path = DEFAULT_STATE, log_path: Path = DEFAULT_LOG):
        # ``enabled`` means that a human may arm this separate controller.  It
        # does not start a cycle, connect MT5, or send an order by itself.
        self.bot = MechanicalBot(config or BotConfig(enabled=True))
        self.adapter = adapter
        self.snapshot_path, self.state_path, self.log_path = snapshot_path, state_path, log_path
        self._runner: Thread | None = None
        self._runner_stop = Event()
        self._runner_lock = Lock()
        self._runner_interval_seconds = 15.0
        self._restore_state()

    def status(self) -> dict[str, Any]:
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
                "account": account, "cycle": cycle, "m5_m1": "DIAGNOSTIC_ONLY_NO_VETO"}

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
        self.bot.arm()
        self._persist_state()
        self._record("ARMED")
        if self.adapter is not None and bool(getattr(self.adapter, "execution_enabled", False)):
            self.start_runner()
        return self.status()

    def disarm(self) -> dict[str, Any]:
        self.stop_runner()
        self.bot.stop()
        self._persist_state()
        self._record("OFF")
        return self.status()

    def close_cycle(self) -> dict[str, Any]:
        if self.bot.cycle is None:
            return self.status()
        return self._execute("CLOSE_ALL", "manual_close")

    def tick(self) -> dict[str, Any]:
        """Run one bounded decision tick; callers schedule it, never a hidden loop."""
        if self.adapter is None:
            raise RuntimeError("MT5 adapter is not configured")
        snapshot = self._load_snapshot()
        candles = self.adapter.closed_m15_candles(self.bot.config.symbol)
        stochastic = stochastic_14_3_3(candles, self.bot.config)
        account = self.adapter.account_status()
        now = datetime.now(timezone.utc)
        if self.bot.cycle is None:
            price = self.adapter.tick_price(self.bot.config.symbol, "BUY")
            action = self.bot.decide_entry(snapshot, stochastic, price, account.balance, now) if snapshot else None
        else:
            price = self.adapter.tick_price(self.bot.config.symbol, self.bot.cycle.direction)
            action = self.bot.monitor(price, self.adapter.positions())
        if action is None:
            return self.status()
        return self._execute(action.kind, action.reason, action=action)

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

    def _run(self) -> None:
        while not self._runner_stop.is_set():
            try:
                self.tick()
            except Exception as exc:
                self.bot.state = BotState.ERROR
                self._persist_state()
                self._record("RUNNER_ERROR", error=str(exc))
                return
            if self._runner_stop.wait(self._runner_interval_seconds):
                return

    def _execute(self, kind: str, reason: str, *, action: Any | None = None) -> dict[str, Any]:
        if self.adapter is None:
            raise RuntimeError("MT5 adapter is not configured")
        if action is None:
            from mechanical_bot.core import BotAction
            action = BotAction(kind, reason)
        try:
            results = self.adapter.execute(action, symbol=self.bot.config.symbol, magic_number=self.bot.config.magic_number)
        except Exception:
            # An uncertain broker response must never be retried as an OPEN.
            # Preserve the cycle for audit, but require an explicit operator
            # action before another decision tick.
            self.bot.state = BotState.ERROR
            self._persist_state()
            self._record("EXECUTION_ERROR", reason=reason)
            raise
        if kind == "CLOSE_ALL":
            self.bot.complete_close()
        self._persist_state()
        self._record(kind, reason=reason, results=results)
        return self.status()

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
            return Snapshot(str(raw["direction"]), float(raw["probability"]), bool(raw["confirmed"]),
                            datetime.fromisoformat(str(raw["asof_time"]).replace("Z", "+00:00")), str(raw.get("symbol", self.bot.config.symbol)))
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


__all__ = ["MechanicalBotService"]
