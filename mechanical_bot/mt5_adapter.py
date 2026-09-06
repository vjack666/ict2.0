"""MT5 boundary for the standalone mechanical bot.

MetaTrader is imported only when the adapter is constructed.  Nothing in this
module starts a terminal or sends an order unless ``execution_enabled`` is
explicitly true and ``execute`` receives an action from the pure core.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from mechanical_bot.core import BotAction, Candle, Position


@dataclass(frozen=True)
class AccountStatus:
    login: int
    server: str
    balance: float
    equity: float
    is_demo: bool


class MT5Adapter:
    def __init__(self, *, terminal_path: str | None = None, execution_enabled: bool = False, mt5: Any | None = None):
        if mt5 is None:
            try:
                import MetaTrader5 as mt5_module
            except ImportError as exc:
                raise RuntimeError("MetaTrader5 is unavailable in this Python runtime") from exc
            mt5 = mt5_module
        self._mt5 = mt5
        self._path = terminal_path
        self.execution_enabled = execution_enabled

    def connect(self) -> None:
        kwargs = {} if self._path is None else {"path": self._path}
        if not self._mt5.initialize(**kwargs):
            raise RuntimeError(f"MT5 initialize failed: {self._mt5.last_error()}")

    def close(self) -> None:
        self._mt5.shutdown()

    def account_status(self) -> AccountStatus:
        info = self._mt5.account_info()
        if info is None:
            raise RuntimeError("MT5 account is not available")
        # MT5 reports trade_mode=0 for demo in the official Python API.
        demo_mode = getattr(self._mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
        return AccountStatus(int(info.login), str(info.server), float(info.balance), float(info.equity), getattr(info, "trade_mode", None) == demo_mode)

    def account_balance(self) -> float:
        return self.account_status().balance

    def positions(self) -> Iterable[Position]:
        rows = self._mt5.positions_get() or ()
        buy_type = getattr(self._mt5, "POSITION_TYPE_BUY", 0)
        return [
            Position(str(row.symbol), int(row.magic), "BUY" if row.type == buy_type else "SELL", float(row.volume), float(row.price_open), float(row.profit))
            for row in rows
        ]

    def tick_price(self, symbol: str, side: str) -> float:
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"MT5 tick unavailable for {symbol}")
        return float(tick.ask if side == "BUY" else tick.bid)

    def closed_m15_candles(self, symbol: str, count: int = 80) -> list[Candle]:
        rates = self._mt5.copy_rates_from_pos(symbol, self._mt5.TIMEFRAME_M15, 1, count)
        if rates is None or len(rates) < count:
            raise RuntimeError(f"MT5 closed M15 candles unavailable for {symbol}")
        return [Candle(float(row["high"]), float(row["low"]), float(row["close"])) for row in rates]

    def execute(self, action: BotAction, *, symbol: str, magic_number: int) -> list[dict[str, Any]]:
        if not self.execution_enabled:
            raise RuntimeError("order execution is disabled in mechanical bot configuration")
        if action.kind == "OPEN":
            return [self._open(action, symbol, magic_number)]
        if action.kind == "CLOSE_ALL":
            return self._close_all(symbol, magic_number)
        raise ValueError(f"unsupported bot action: {action.kind}")

    def _open(self, action: BotAction, symbol: str, magic_number: int) -> dict[str, Any]:
        side = action.side or ""
        if side not in {"BUY", "SELL"} or action.volume is None:
            raise ValueError("OPEN requires a side and volume")
        order_type = self._mt5.ORDER_TYPE_BUY if side == "BUY" else self._mt5.ORDER_TYPE_SELL
        request = {"action": self._mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": float(action.volume), "type": order_type,
                   "price": self.tick_price(symbol, side), "magic": int(magic_number), "comment": "ICT mechanical bot"}
        result = self._mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"MT5 order_send failed: {self._mt5.last_error()}")
        self._require_success(result, "open")
        return {"kind": "OPEN", "retcode": int(result.retcode), "order": int(getattr(result, "order", 0)), "deal": int(getattr(result, "deal", 0))}

    def _close_all(self, symbol: str, magic_number: int) -> list[dict[str, Any]]:
        rows = [row for row in (self._mt5.positions_get(symbol=symbol) or ()) if int(row.magic) == int(magic_number)]
        buy_type = getattr(self._mt5, "POSITION_TYPE_BUY", 0)
        results = []
        for row in rows:
            close_side = "SELL" if row.type == buy_type else "BUY"
            order_type = self._mt5.ORDER_TYPE_SELL if close_side == "SELL" else self._mt5.ORDER_TYPE_BUY
            request = {"action": self._mt5.TRADE_ACTION_DEAL, "position": int(row.ticket), "symbol": symbol, "volume": float(row.volume),
                       "type": order_type, "price": self.tick_price(symbol, close_side), "magic": int(magic_number), "comment": "ICT mechanical bot close"}
            result = self._mt5.order_send(request)
            if result is None:
                raise RuntimeError(f"MT5 close failed: {self._mt5.last_error()}")
            self._require_success(result, f"close ticket {row.ticket}")
            results.append({"kind": "CLOSE", "ticket": int(row.ticket), "retcode": int(result.retcode), "deal": int(getattr(result, "deal", 0))})
        return results

    @staticmethod
    def _require_success(result: Any, operation: str) -> None:
        # TRADE_RETCODE_DONE and DONE_PARTIAL.  Anything else is uncertain or
        # rejected and must propagate to the service's ERROR state.
        retcode = int(getattr(result, "retcode", -1))
        if retcode not in {10009, 10010}:
            raise RuntimeError(f"MT5 {operation} rejected with retcode={retcode}")


__all__ = ["AccountStatus", "MT5Adapter"]
