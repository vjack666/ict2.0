"""Deterministic mechanical bot core.

This module intentionally has no MetaTrader dependency and never sends an order.
An adapter may consume ``BotAction`` only after explicit user arming.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, Mapping, Protocol, Sequence


class BotState(str, Enum):
    OFF = "OFF"
    ARMED = "ARMED"
    WAIT_SIGNAL = "WAIT_SIGNAL"
    WAIT_STOCHASTIC = "WAIT_STOCHASTIC"
    INITIAL_ENTRY = "INITIAL_ENTRY"
    REENTRY_1 = "REENTRY_1"
    REENTRY_2 = "REENTRY_2"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class BotConfig:
    symbol: str = "EURUSD"
    magic_number: int = 26090615
    enabled: bool = False
    min_probability: float = 0.70
    stale_after: timedelta = timedelta(minutes=20)
    k_period: int = 14
    k_smoothing: int = 3
    d_period: int = 3
    oversold: float = 20.0
    overbought: float = 80.0
    pip_size: float = 0.0001
    initial_lot: float = 0.10
    reentry_lots: tuple[float, float] = (0.20, 0.30)
    reentry_pips: tuple[float, float] = (20.0, 40.0)
    take_profit_usd: float = 60.0
    max_loss_balance_pct: float = 0.02

    def __post_init__(self) -> None:
        if not 0 < self.min_probability <= 1:
            raise ValueError("min_probability must be in (0, 1]")
        if self.pip_size <= 0 or self.initial_lot <= 0:
            raise ValueError("pip_size and initial_lot must be positive")
        if len(self.reentry_lots) != 2 or len(self.reentry_pips) != 2:
            raise ValueError("exactly two reentries are required")


@dataclass(frozen=True)
class Snapshot:
    direction: str
    probability: float
    confirmed: bool
    asof_time: datetime
    symbol: str = "EURUSD"

    def normalized_direction(self) -> str:
        value = self.direction.upper()
        if value in {"BUY", "BULLISH", "LONG"}:
            return "BUY"
        if value in {"SELL", "BEARISH", "SHORT"}:
            return "SELL"
        return "UNKNOWN"


class SnapshotRejected(ValueError):
    pass


def validate_snapshot(snapshot: Snapshot, config: BotConfig, now: datetime) -> str:
    """Return BUY/SELL only for a fresh confirmed snapshot.

    No M5 or M1 field is inspected: they are deliberately diagnostic-only.
    """
    if snapshot.symbol != config.symbol:
        raise SnapshotRejected("snapshot symbol differs from configured symbol")
    if not snapshot.confirmed:
        raise SnapshotRejected("snapshot is not confirmed")
    asof = _utc(snapshot.asof_time)
    if _utc(now) - asof > config.stale_after:
        raise SnapshotRejected("snapshot is stale")
    direction = snapshot.normalized_direction()
    if direction == "UNKNOWN" or snapshot.probability < config.min_probability:
        raise SnapshotRejected("snapshot has insufficient directional probability")
    return direction


@dataclass(frozen=True)
class Candle:
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class StochasticReading:
    k: float
    d: float
    previous_k: float
    previous_d: float

    def crossed_up_from_oversold(self, threshold: float = 20.0) -> bool:
        return self.previous_k <= threshold and self.previous_d <= threshold and self.previous_k <= self.previous_d and self.k > self.d

    def crossed_down_from_overbought(self, threshold: float = 80.0) -> bool:
        return self.previous_k >= threshold and self.previous_d >= threshold and self.previous_k >= self.previous_d and self.k < self.d


def stochastic_14_3_3(candles: Sequence[Candle], config: BotConfig = BotConfig()) -> StochasticReading | None:
    """Closed-candle stochastic 14,3,3; returns None until enough candles exist."""
    required = config.k_period + config.k_smoothing + config.d_period
    if len(candles) < required:
        return None
    raw_k: list[float] = []
    for end in range(config.k_period, len(candles) + 1):
        window = candles[end - config.k_period:end]
        high, low = max(c.high for c in window), min(c.low for c in window)
        raw_k.append(50.0 if high == low else 100.0 * (window[-1].close - low) / (high - low))
    smooth_k = _sma(raw_k, config.k_smoothing)
    smooth_d = _sma(smooth_k, config.d_period)
    if len(smooth_d) < 2:
        return None
    # Align K with the D observation to avoid comparing mismatched periods.
    return StochasticReading(k=smooth_k[-1], d=smooth_d[-1], previous_k=smooth_k[-2], previous_d=smooth_d[-2])


def _sma(values: Sequence[float], period: int) -> list[float]:
    return [sum(values[i - period:i]) / period for i in range(period, len(values) + 1)]


@dataclass(frozen=True)
class Position:
    symbol: str
    magic_number: int
    side: str
    volume: float
    entry_price: float
    profit_usd: float


class BrokerView(Protocol):
    def account_balance(self) -> float: ...
    def positions(self) -> Iterable[Position]: ...


@dataclass(frozen=True)
class BotAction:
    kind: str
    reason: str
    side: str | None = None
    volume: float | None = None


@dataclass
class Cycle:
    direction: str
    initial_price: float
    balance_at_start: float
    signal_time: datetime
    entries: int = 1


@dataclass
class MechanicalBot:
    config: BotConfig = field(default_factory=BotConfig)
    state: BotState = BotState.OFF
    cycle: Cycle | None = None
    last_closed_signal_time: datetime | None = None

    def arm(self) -> None:
        """Explicitly move an enabled bot into the ready state."""
        if not self.config.enabled:
            raise RuntimeError("bot is disabled by configuration")
        self.state = BotState.ARMED

    def stop(self) -> None:
        """Disarm without requesting a broker operation."""
        self.state, self.cycle = BotState.OFF, None

    def decide_entry(self, snapshot: Snapshot, stochastic: StochasticReading | None, price: float, balance: float, now: datetime) -> BotAction | None:
        """Return an initial OPEN action only for a new approved M15 cross."""
        if self.state == BotState.OFF:
            return None
        direction = validate_snapshot(snapshot, self.config, now)
        if self.last_closed_signal_time is not None and _utc(snapshot.asof_time) <= _utc(self.last_closed_signal_time):
            return None
        self.state = BotState.WAIT_STOCHASTIC
        if stochastic is None:
            return None
        allowed = (direction == "BUY" and stochastic.crossed_up_from_oversold(self.config.oversold)) or (direction == "SELL" and stochastic.crossed_down_from_overbought(self.config.overbought))
        if not allowed:
            return None
        if self.cycle is not None:
            return None
        self.cycle = Cycle(direction=direction, initial_price=price, balance_at_start=balance, signal_time=snapshot.asof_time)
        self.state = BotState.INITIAL_ENTRY
        return BotAction("OPEN", "confirmed_snapshot_and_m15_stochastic_cross", direction, self.config.initial_lot)

    def monitor(self, price: float, positions: Iterable[Position]) -> BotAction | None:
        """Evaluate only this bot's positions; caller executes returned action explicitly."""
        if self.cycle is None or self.state == BotState.CLOSING:
            return None
        own = [p for p in positions if p.symbol == self.config.symbol and p.magic_number == self.config.magic_number]
        if not own:
            # A recovered/incomplete cycle without its own broker positions is
            # ambiguous.  Never infer a re-entry from it; require review.
            self.state = BotState.ERROR
            return None
        profit = sum(p.profit_usd for p in own)
        if profit >= self.config.take_profit_usd:
            self.state = BotState.CLOSING
            return BotAction("CLOSE_ALL", "take_profit_aggregate")
        if profit <= -(self.cycle.balance_at_start * self.config.max_loss_balance_pct):
            self.state = BotState.CLOSING
            return BotAction("CLOSE_ALL", "max_floating_loss")
        if self.cycle.entries >= 3:
            return None
        step = self.cycle.entries - 1
        adverse = self.config.reentry_pips[step] * self.config.pip_size
        reached = price <= self.cycle.initial_price - adverse if self.cycle.direction == "BUY" else price >= self.cycle.initial_price + adverse
        if not reached:
            return None
        self.cycle.entries += 1
        self.state = BotState.REENTRY_1 if self.cycle.entries == 2 else BotState.REENTRY_2
        return BotAction("OPEN", f"adverse_reentry_{self.cycle.entries - 1}", self.cycle.direction, self.config.reentry_lots[step])

    def complete_close(self) -> None:
        """Record completion after the adapter has confirmed every close."""
        if self.cycle is not None:
            self.last_closed_signal_time = self.cycle.signal_time
        self.cycle = None
        self.state = BotState.CLOSED


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
