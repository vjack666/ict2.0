"""MT5 boundary for the standalone mechanical bot.

MetaTrader is imported only when the adapter is constructed.  Nothing in this
module starts a terminal or sends an order unless ``execution_enabled`` is
explicitly true and ``execute`` receives an action from the pure core.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Iterable

from mechanical_bot.blackbox import BlackBoxJournal, BlackBoxWriteError, canonical_hash
from mechanical_bot.core import BotAction, Candle, Position


@dataclass(frozen=True)
class AccountStatus:
    login: int
    server: str
    balance: float
    equity: float
    is_demo: bool


class MT5Adapter:
    def __init__(self, *, terminal_path: str | None = None, execution_enabled: bool = False, mt5: Any | None = None,
                 blackbox: BlackBoxJournal | None = None, demo_account_login: int | None = None,
                 demo_account_server: str | None = None, server_utc_offset_seconds: int = 0):
        if mt5 is None:
            try:
                import MetaTrader5 as mt5_module
            except ImportError as exc:
                raise RuntimeError("MetaTrader5 is unavailable in this Python runtime") from exc
            mt5 = mt5_module
        self._mt5 = mt5
        self._path = terminal_path
        # Never interpret a string such as "false" as permission to trade.
        self.execution_enabled = execution_enabled is True
        self._lock = RLock()
        self.server_utc_offset_seconds = int(server_utc_offset_seconds)
        self._blackbox = blackbox
        self._demo_account_login: int | None = None
        self._demo_account_server: str | None = None
        if demo_account_login is not None or demo_account_server is not None:
            self.configure_demo_guard(demo_account_login, demo_account_server)

    def set_blackbox(self, journal: BlackBoxJournal) -> None:
        """Attach the mandatory durable pre-send journal before arming."""
        if not isinstance(journal, BlackBoxJournal):
            raise TypeError("black-box journal is required")
        with self._lock:
            self._blackbox = journal

    def configure_demo_guard(self, login: int | None, server: str | None) -> None:
        """Pin execution to one explicit demo account; blank values are rejected."""
        if login is None or not isinstance(login, int) or login <= 0 or not isinstance(server, str) or not server.strip():
            raise ValueError("demo execution requires a positive login and server")
        with self._lock:
            self._demo_account_login = int(login)
            self._demo_account_server = server.strip()

    def connect(self) -> None:
        with self._lock:
            kwargs = {} if self._path is None else {"path": self._path}
            if not self._mt5.initialize(**kwargs):
                raise RuntimeError(f"MT5 initialize failed: {self._mt5.last_error()}")

    def close(self) -> None:
        with self._lock:
            self._mt5.shutdown()

    def account_status(self) -> AccountStatus:
        with self._lock:
            info = self._mt5.account_info()
            if info is None:
                raise RuntimeError("MT5 account is not available")
            demo_mode = getattr(self._mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
            return AccountStatus(int(info.login), str(info.server), float(info.balance), float(info.equity), getattr(info, "trade_mode", None) == demo_mode)

    def account_balance(self) -> float:
        return self.account_status().balance

    def positions(self) -> Iterable[Position]:
        with self._lock:
            rows = self._mt5.positions_get() or ()
            buy_type = getattr(self._mt5, "POSITION_TYPE_BUY", 0)
            return [
                Position(str(row.symbol), int(row.magic), "BUY" if row.type == buy_type else "SELL", float(row.volume), float(row.price_open), float(row.profit))
                for row in rows
            ]

    def tick_price(self, symbol: str, side: str) -> float:
        with self._lock:
            tick = self._mt5.symbol_info_tick(symbol)
            if tick is None:
                raise RuntimeError(f"MT5 tick unavailable for {symbol}")
            # MT5 exposes Unix seconds on live ticks.  Test doubles without a
            # timestamp remain usable, but a real stale terminal fails closed.
            if hasattr(tick, "time"):
                self._assert_recent_epoch(getattr(tick, "time"), 30, "MT5 tick", self.server_utc_offset_seconds)
            return float(tick.ask if side == "BUY" else tick.bid)

    def closed_m15_candles(self, symbol: str, count: int = 80) -> list[Candle]:
        with self._lock:
            rates = self._mt5.copy_rates_from_pos(symbol, self._mt5.TIMEFRAME_M15, 1, count)
            if rates is None or len(rates) < count:
                raise RuntimeError(f"MT5 closed M15 candles unavailable for {symbol}")
            try:
                self._assert_recent_epoch(rates[-1]["time"], 1_800, "MT5 closed M15 candle", self.server_utc_offset_seconds)
            except (IndexError, KeyError, TypeError):
                # MT5 native structured arrays always have ``time``.  Keep
                # lightweight test fixtures compatible while live feeds retain
                # the freshness guard above.
                pass
            return [Candle(float(row["high"]), float(row["low"]), float(row["close"])) for row in rates]

    def execute(self, action: BotAction, *, symbol: str, magic_number: int, correlation_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if not self.execution_enabled:
                raise RuntimeError("order execution is disabled in mechanical bot configuration")
            if self._blackbox is None:
                raise RuntimeError("order execution requires a configured black-box journal")
            if action.kind == "OPEN":
                return [self._open(action, symbol, magic_number, correlation_id)]
            if action.kind == "CLOSE_ALL":
                return self._close_all(symbol, magic_number, correlation_id)
            raise ValueError(f"unsupported bot action: {action.kind}")

    def _open(self, action: BotAction, symbol: str, magic_number: int, correlation_id: str | None) -> dict[str, Any]:
        side = action.side or ""
        if side not in {"BUY", "SELL"} or action.volume is None:
            raise ValueError("OPEN requires a side and volume")
        order_type = self._mt5.ORDER_TYPE_BUY if side == "BUY" else self._mt5.ORDER_TYPE_SELL
        request = {"action": self._mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": float(action.volume), "type": order_type,
                   "price": self.tick_price(symbol, side), "magic": int(magic_number), "comment": "ICT mechanical bot"}
        result = self._send(request, operation="OPEN", correlation_id=correlation_id)
        if result is None:
            raise RuntimeError(f"MT5 order_send failed: {self._mt5.last_error()}")
        self._require_success(result, "open")
        return {"kind": "OPEN", "retcode": int(result.retcode), "order": int(getattr(result, "order", 0)), "deal": int(getattr(result, "deal", 0))}

    def _close_all(self, symbol: str, magic_number: int, correlation_id: str | None) -> list[dict[str, Any]]:
        rows = [row for row in (self._mt5.positions_get(symbol=symbol) or ()) if int(row.magic) == int(magic_number)]
        if not rows:
            raise RuntimeError("MT5 close reconciliation failed: no matching bot positions")
        buy_type = getattr(self._mt5, "POSITION_TYPE_BUY", 0)
        results = []
        for row in rows:
            close_side = "SELL" if row.type == buy_type else "BUY"
            order_type = self._mt5.ORDER_TYPE_SELL if close_side == "SELL" else self._mt5.ORDER_TYPE_BUY
            request = {"action": self._mt5.TRADE_ACTION_DEAL, "position": int(row.ticket), "symbol": symbol, "volume": float(row.volume),
                       "type": order_type, "price": self.tick_price(symbol, close_side), "magic": int(magic_number), "comment": "ICT mechanical bot close"}
            result = self._send(request, operation="CLOSE", correlation_id=correlation_id)
            if result is None:
                raise RuntimeError(f"MT5 close failed: {self._mt5.last_error()}")
            self._require_success(result, f"close ticket {row.ticket}")
            results.append({"kind": "CLOSE", "ticket": int(row.ticket), "retcode": int(result.retcode), "deal": int(getattr(result, "deal", 0))})
        remaining = [row for row in (self._mt5.positions_get(symbol=symbol) or ()) if int(row.magic) == int(magic_number)]
        if remaining:
            raise RuntimeError("MT5 close reconciliation failed: matching bot positions remain")
        return results

    def _send(self, request: dict[str, Any], *, operation: str, correlation_id: str | None) -> Any:
        """Record the exact request before the irreversible MT5 call.

        A journal failure occurs before ``order_send`` and therefore blocks the
        request.  Broker failures and unusual results are also retained with
        the MT5 ``last_error`` for later reconciliation.
        """
        self._assert_demo_guard()
        if self._blackbox is None:  # defensive guard for direct private calls
            raise RuntimeError("order execution requires a configured black-box journal")
        request_hash = canonical_hash(request)
        try:
            self._blackbox.record("ORDER_REQUEST", correlation_id=correlation_id, operation=operation,
                                  request=request, request_hash=request_hash)
        except BlackBoxWriteError as exc:
            raise RuntimeError("order blocked: black-box pre-send persistence failed") from exc
        try:
            # The documented API takes one positional request mapping.
            # On 5.0.5735, request=<mapping> silently produces an empty
            # TradeRequest and retcode 10013. Never retry another signature
            # after a send: a broker response may be uncertain.
            result = self._mt5.order_send(request)
        except Exception as exc:
            self._record_outcome(correlation_id, operation, request_hash, result=None, error=str(exc), exception_type=type(exc).__name__)
            raise
        if result is None:
            last_error = self._last_error()
            self._record_outcome(correlation_id, operation, request_hash, result=None, last_error=last_error)
            raise RuntimeError(f"MT5 {operation.lower()} failed: {last_error}")
        self._record_outcome(correlation_id, operation, request_hash, result=result, last_error=self._last_error())
        return result

    def _record_outcome(self, correlation_id: str | None, operation: str, request_hash: str, *, result: Any,
                        last_error: Any | None = None, error: str | None = None, exception_type: str | None = None) -> None:
        assert self._blackbox is not None
        try:
            self._blackbox.record("ORDER_RESULT", correlation_id=correlation_id, operation=operation,
                                  request_hash=request_hash, outcome="NONE" if result is None else "RESULT",
                                  result=result, result_hash=None if result is None else canonical_hash(result),
                                  result_hash_scope="full_canonical_json", last_error=last_error,
                                  error=error, exception_type=exception_type)
        except BlackBoxWriteError as exc:
            # The broker call has happened but its evidence is now incomplete:
            # surface an ERROR to prevent any automated retry or further order.
            raise RuntimeError("broker response received but black-box result persistence failed") from exc

    def _assert_demo_guard(self) -> None:
        if self._demo_account_login is None:
            return
        current = self.account_status()
        if not current.is_demo or current.login != self._demo_account_login or current.server != self._demo_account_server:
            raise RuntimeError("MT5 execution blocked: pinned demo account no longer matches")

    def _last_error(self) -> Any:
        try:
            return self._mt5.last_error()
        except Exception as exc:
            return f"last_error unavailable: {exc}"

    @staticmethod
    def _assert_recent_epoch(value: Any, max_age_seconds: int, source: str, server_utc_offset_seconds: int = 0) -> None:
        try:
            timestamp = float(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{source} timestamp is invalid") from exc
        age = (datetime.now(timezone.utc) - datetime.fromtimestamp(timestamp - server_utc_offset_seconds, tz=timezone.utc)).total_seconds()
        if age < -5 or age > max_age_seconds:
            raise RuntimeError(f"{source} is stale or from the future (age_seconds={age:.1f})")

    @staticmethod
    def _require_success(result: Any, operation: str) -> None:
        # TRADE_RETCODE_DONE and DONE_PARTIAL.  Anything else is uncertain or
        # rejected and must propagate to the service's ERROR state.
        retcode = int(getattr(result, "retcode", -1))
        if retcode not in {10009, 10010}:
            raise RuntimeError(f"MT5 {operation} rejected with retcode={retcode}")


__all__ = ["AccountStatus", "MT5Adapter"]
