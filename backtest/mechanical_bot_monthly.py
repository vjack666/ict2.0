"""Causal, diagnostic-only monthly replay for the standalone mechanical bot.

The module deliberately does not import MetaTrader or the execution adapter.  It
freezes a structural proxy before each trading day, then consumes M1 bars in
time order only after a London/New York window opens.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Callable, Iterable

import pandas as pd

from engine.bos import StructureConfig, detect_market_structure
from engine.ltf_canonical_feed import build_ltf_canonical_feed
from engine.market_object import ObjectState, ObjectType
from engine.plan import build_context_stack, top_down_allows_trade

UTC = timezone.utc
GUAYAQUIL = ZoneInfo("America/Guayaquil")
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")
# Historical depths are explicit, past-only and large enough for the relevant
# structure layer.  They prevent a daily snapshot from rebuilding years of
# M15 lifecycle state while preserving a multi-week M15 FVG reference.
CONTEXT_LOOKBACK_BARS = {"D1": 520, "H4": 780, "H1": 1200, "M15": 800}


@dataclass(frozen=True)
class MonthlyBotConfig:
    symbol: str = "EURUSD"
    starting_balance: float = 5_000.0
    pip_size: float = 0.0001
    dollars_per_pip_per_lot: float = 10.0
    lots: tuple[float, float, float] = (0.10, 0.10, 0.10)
    reentry_pips: tuple[float, float] = (20.0, 40.0)
    take_profit_usd: float = 60.0
    loss_balance_pct: float = 0.03
    spread_pips: float = 1.0
    slippage_pips: float = 0.3
    commission_per_lot_side: float = 5.0


@dataclass(frozen=True)
class FrozenContext:
    asof_time: datetime
    direction: str
    d1_direction: str
    h4_direction: str
    h1_direction: str
    m15_direction: str
    fvg_direction: str | None
    fvg_low: float | None
    fvg_high: float | None

    @property
    def eligible(self) -> bool:
        return self.direction in {"BUY", "SELL"} and self.fvg_direction == self.direction


@dataclass
class SimPosition:
    side: str
    volume: float
    raw_entry_price: float
    entry_price: float
    entry_time: datetime
    open_commission: float


@dataclass
class SimCycle:
    direction: str
    signal_time: datetime
    balance_at_start: float
    initial_price: float
    positions: list[SimPosition]
    session: str


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start: datetime
    end: datetime


def _utc(value: Any) -> datetime:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC").to_pydatetime()


def session_windows(trading_day: date) -> tuple[SessionWindow, SessionWindow]:
    """Return local 08:00–12:00 London and New York windows in UTC.

    ZoneInfo is intentionally used instead of fixed offsets, making DST part of
    the artifact rather than an undocumented assumption.
    """
    def window(name: str, zone: ZoneInfo) -> SessionWindow:
        start = datetime.combine(trading_day, time(8), tzinfo=zone).astimezone(UTC)
        end = datetime.combine(trading_day, time(12), tzinfo=zone).astimezone(UTC)
        return SessionWindow(name, start, end)
    return window("LONDON", LONDON), window("NEW_YORK", NEW_YORK)


def nightly_cutoff(trading_day: date) -> datetime:
    """20:00 Guayaquil on the prior calendar day, represented in UTC."""
    prior = trading_day - timedelta(days=1)
    return datetime.combine(prior, time(20), tzinfo=GUAYAQUIL).astimezone(UTC)


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"time", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"OHLC frame missing columns: {sorted(missing)}")
    result = frame.loc[:, ["time", "open", "high", "low", "close"]].copy()
    result["time"] = pd.to_datetime(result["time"], utc=True)
    result = result.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
    if result.empty:
        raise ValueError("OHLC frame is empty")
    return result


def _completed(frame: pd.DataFrame, cutoff: datetime, duration: timedelta) -> pd.DataFrame:
    # Timestamp is the bar open.  A bar may influence a snapshot only after its
    # own close; this is the no-look-ahead boundary for all TFs.
    return frame[frame["time"] + pd.Timedelta(duration) <= pd.Timestamp(cutoff)].copy()


def _canonical_prefix(frame: pd.DataFrame, cutoff: datetime, duration: timedelta, limit: int) -> pd.DataFrame:
    """Build the engine-owned, closed-only prefix for one timeframe."""
    prefix = _completed(frame, cutoff, duration).tail(limit).reset_index(drop=True)
    if prefix.empty:
        return prefix
    return detect_market_structure(prefix.reset_index(drop=True), StructureConfig()).frame


def freeze_context(frames: dict[str, pd.DataFrame], cutoff: datetime) -> FrozenContext:
    """Freeze the engine's canonical D1/H4/H1/M15 context and FVG objects.

    The backtest does not detect trends or FVGs. It passes only completed bars
    into the engine APIs, then records their published point-in-time result.
    """
    durations = {"D1": timedelta(days=1), "H4": timedelta(hours=4), "H1": timedelta(hours=1), "M15": timedelta(minutes=15)}
    canonical = {
        tf: _canonical_prefix(_normalise(frames[tf]), cutoff, duration, CONTEXT_LOOKBACK_BARS[tf])
        for tf, duration in durations.items()
    }
    stack = build_context_stack(canonical, cutoff, tfs=("D1", "H4", "H1", "M15"))
    trends = {tf: str(stack[tf].get("trend", "RANGING")) for tf in ("D1", "H4", "H1", "M15")}
    direction = "BUY" if set(trends.values()) == {"BULLISH"} else "SELL" if set(trends.values()) == {"BEARISH"} else "UNKNOWN"
    sign = 1 if direction == "BUY" else -1
    allowed, _reason = top_down_allows_trade(stack, sign, require_pd=False, require_ltf=False) if direction != "UNKNOWN" else (False, "unaligned")
    feed = build_ltf_canonical_feed(canonical, cutoff, exec_tf="M15", sequence_tf="H1", symbol="EURUSD", include_sequence=False, touch_lifecycle=True)
    fvg = next((obj for obj in reversed(feed["zones"].get("M15", [])) if obj.type is ObjectType.FVG and obj.direction == sign and obj.state is ObjectState.ACTIVE), None)
    fvg_direction = direction if fvg is not None else None
    return FrozenContext(
        asof_time=cutoff,
        direction=direction if allowed and fvg is not None else "UNKNOWN",
        d1_direction=trends["D1"], h4_direction=trends["H4"], h1_direction=trends["H1"], m15_direction=trends["M15"],
        fvg_direction=fvg_direction,
        fvg_low=None if fvg is None else float(fvg.zone_low),
        fvg_high=None if fvg is None else float(fvg.zone_high),
    )

def stochastic_reading(m15: pd.DataFrame) -> tuple[float, float, float, float] | None:
    """Closed-candle Stochastic 14,3,3, returning K,D,previous K,D."""
    if len(m15) < 19:  # 14 raw K + smoothing and two aligned D observations
        return None
    raw: list[float] = []
    for end in range(14, len(m15) + 1):
        window = m15.iloc[end - 14:end]
        high, low = float(window.high.max()), float(window.low.min())
        raw.append(50.0 if high == low else 100.0 * (float(window.iloc[-1].close) - low) / (high - low))
    smooth_k = [sum(raw[i - 3:i]) / 3 for i in range(3, len(raw) + 1)]
    smooth_d = [sum(smooth_k[i - 3:i]) / 3 for i in range(3, len(smooth_k) + 1)]
    if len(smooth_d) < 2:
        return None
    return smooth_k[-1], smooth_d[-1], smooth_k[-2], smooth_d[-2]


def stochastic_cross(m15: pd.DataFrame, direction: str) -> bool:
    reading = stochastic_reading(m15)
    if reading is None:
        return False
    k, d, previous_k, previous_d = reading
    if direction == "BUY":
        return previous_k <= 20 and previous_d <= 20 and previous_k <= previous_d and k > d
    return direction == "SELL" and previous_k >= 80 and previous_d >= 80 and previous_k >= previous_d and k < d


class MonthlyMechanicalBacktest:
    """Pure local replay with one basket at a time and an append-only event list."""
    def __init__(self, frames: dict[str, pd.DataFrame], config: MonthlyBotConfig = MonthlyBotConfig()):
        required = {"D1", "H4", "H1", "M15", "M1"}
        missing = required - set(frames)
        if missing:
            raise ValueError(f"missing timeframes: {sorted(missing)}")
        self.frames = {tf: _normalise(value) for tf, value in frames.items()}
        self.config = config
        self.events: list[dict[str, Any]] = []
        self.balance = config.starting_balance
        self.peak_equity = self.balance
        self.max_drawdown_usd = 0.0
        self.cycle: SimCycle | None = None
        self._next_id = 0

    def _event(self, kind: str, at: datetime, **payload: Any) -> None:
        self._next_id += 1
        self.events.append({"id": f"MB-{self._next_id:06d}", "kind": kind, "asof_time": _utc(at).isoformat(), **payload})

    def run(self, start: date, end: date, progress: Callable[[date, int, int], None] | None = None) -> dict[str, Any]:
        days = list(pd.date_range(start, end, freq="D"))
        for position, day in enumerate(days, 1):
            trading_day = day.date()
            cutoff = nightly_cutoff(trading_day)
            context = freeze_context(self.frames, cutoff)
            self._event("SNAPSHOT", cutoff, trading_day=str(trading_day), context=asdict(context), eligible=context.eligible)
            for window in session_windows(trading_day):
                self._run_window(window, context)
            if progress is not None:
                progress(trading_day, position, len(days))
        # A cycle still open at end-of-month is closed at last available M1,
        # avoiding an unpriced implicit carry into an untested month.
        if self.cycle is not None:
            final = self.frames["M1"].iloc[-1]
            self._close_cycle(_utc(final.time), float(final.close), "month_end_flatten")
        return self.result(start, end)

    def _run_window(self, window: SessionWindow, context: FrozenContext) -> None:
        rows = self.frames["M1"]
        rows = rows[(rows.time >= pd.Timestamp(window.start)) & (rows.time < pd.Timestamp(window.end))]
        # The stochastic only needs the most recent completed M15 readings.
        # Searching the sorted timestamp column avoids repeatedly copying the
        # full multi-year M15 parquet for every simulated M1 bar.
        m15 = self.frames["M15"]
        m15_times = pd.DatetimeIndex(m15["time"])
        if rows.empty:
            return
        # A London cycle can cross into New York.  New York manages it first;
        # if it closes, NY may arm one new cycle of its own.  A cycle opened in
        # this window prevents another entry here after its close.
        opened_in_this_window = False
        pending_entry = False
        last_m15_stamp: pd.Timestamp | None = None
        context_rejected_logged = False
        for _, bar in rows.iterrows():
            now = _utc(bar.time)
            if self.cycle is not None:
                self._manage_bar(now, bar)
                continue
            if opened_in_this_window:
                continue
            if not context.eligible:
                if not context_rejected_logged:
                    self._event("SESSION_ABSTAIN", now, session=window.name, reason="frozen_context_not_aligned_or_no_active_fvg")
                    context_rejected_logged = True
                continue
            if pending_entry:
                self._open_initial(now, float(bar.open), context.direction, window.name, context.asof_time)
                opened_in_this_window = True
                pending_entry = False
                continue
            closed_through = pd.Timestamp(now) - pd.Timedelta(minutes=15)
            end = m15_times.searchsorted(closed_through, side="right")
            # 50 rows is deliberately above the 19 required by Stochastic
            # 14,3,3, while still containing closed bars only.
            known = m15.iloc[max(0, end - 50):end]
            if known.empty:
                continue
            stamp = known.iloc[-1].time
            if last_m15_stamp is not None and stamp == last_m15_stamp:
                continue
            last_m15_stamp = stamp
            if stochastic_cross(known, context.direction):
                pending_entry = True
                self._event("STOCHASTIC_CROSS", now, session=window.name, direction=context.direction, m15_closed_at=_utc(stamp + pd.Timedelta(minutes=15)).isoformat())
        if self.cycle is None and not opened_in_this_window:
            self._event("SESSION_NO_ENTRY", window.end, session=window.name)
    def _filled_price(self, price: float, side: str, opening: bool) -> float:
        cost = (self.config.spread_pips / 2 + self.config.slippage_pips) * self.config.pip_size
        # Both opening and closing fills are adverse to the trader.
        if (side == "BUY") == opening:
            return price + cost
        return price - cost

    def _open_initial(self, now: datetime, price: float, direction: str, session: str, signal_time: datetime) -> None:
        pos = self._position(now, price, direction, self.config.lots[0])
        self.cycle = SimCycle(direction, signal_time, self.balance, pos.entry_price, [pos], session)
        self._event("ENTRY", now, session=session, direction=direction, volume=pos.volume, price=pos.entry_price, balance_at_start=self.balance)

    def _position(self, now: datetime, price: float, side: str, volume: float) -> SimPosition:
        return SimPosition(side, volume, price, self._filled_price(price, side, True), now, volume * self.config.commission_per_lot_side)

    def _pnl_at(self, position: SimPosition, entry: float, exit_price: float) -> float:
        move = (exit_price - entry) / self.config.pip_size
        if position.side == "SELL":
            move = -move
        return move * self.config.dollars_per_pip_per_lot * position.volume

    def _basket_pnl(self, market: float) -> tuple[float, float, float, float]:
        """Return raw gross, executed gross, net P/L, and all execution costs.

        Marking a basket uses an adverse executable close for every open
        position.  Therefore the dynamic TP/SL sees the same net economics
        that a simulated closure will book, including both commission sides.
        """
        assert self.cycle is not None
        close_market = self._filled_price(market, self.cycle.direction, False)
        raw_gross = sum(self._pnl_at(p, p.raw_entry_price, market) for p in self.cycle.positions)
        executed_gross = sum(self._pnl_at(p, p.entry_price, close_market) for p in self.cycle.positions)
        commissions = sum(p.open_commission + p.volume * self.config.commission_per_lot_side for p in self.cycle.positions)
        net = executed_gross - commissions
        return raw_gross, executed_gross, net, raw_gross - net

    def _manage_bar(self, now: datetime, bar: pd.Series) -> None:
        assert self.cycle is not None
        # Test both extremes.  Where both limits are reachable on an unknown
        # intrabar path, loss is deterministically selected first.
        adverse_market = float(bar.low) if self.cycle.direction == "BUY" else float(bar.high)
        favorable_market = float(bar.high) if self.cycle.direction == "BUY" else float(bar.low)
        _, _, worst, _ = self._basket_pnl(adverse_market)
        _, _, best, _ = self._basket_pnl(favorable_market)
        risk_limit = -(self.cycle.balance_at_start * self.config.loss_balance_pct)
        if worst <= risk_limit:
            self._close_cycle(now, adverse_market, "max_floating_loss")
            return
        if best >= self.config.take_profit_usd:
            self._close_cycle(now, favorable_market, "take_profit_aggregate")
            return
        initial = self.cycle.initial_price
        reentries = len(self.cycle.positions) - 1
        if reentries >= 2:
            return
        threshold = self.config.reentry_pips[reentries] * self.config.pip_size
        reached = adverse_market <= initial - threshold if self.cycle.direction == "BUY" else adverse_market >= initial + threshold
        if reached:
            price = initial - threshold if self.cycle.direction == "BUY" else initial + threshold
            pos = self._position(now, price, self.cycle.direction, self.config.lots[reentries + 1])
            self.cycle.positions.append(pos)
            self._event("REENTRY", now, direction=self.cycle.direction, level=reentries + 1, volume=pos.volume, price=pos.entry_price)
        # Drawdown is recorded on all M1 states, including an open basket.
        equity = self.balance + worst
        self.peak_equity = max(self.peak_equity, equity)
        self.max_drawdown_usd = max(self.max_drawdown_usd, self.peak_equity - equity)

    def _close_cycle(self, now: datetime, market: float, reason: str) -> None:
        assert self.cycle is not None
        # Close price has a second, adverse fill and every position pays its own
        # close-side commission.
        raw_gross, executed_gross, net, execution_cost = self._basket_pnl(market)
        close_commission = sum(p.volume * self.config.commission_per_lot_side for p in self.cycle.positions)
        balance_before = self.balance
        self.balance += net
        self.peak_equity = max(self.peak_equity, self.balance)
        self.max_drawdown_usd = max(self.max_drawdown_usd, self.peak_equity - self.balance)
        self._event("CLOSE", now, session=self.cycle.session, reason=reason, direction=self.cycle.direction, entries=len(self.cycle.positions), raw_gross_pnl_usd=raw_gross, gross_pnl_usd=executed_gross, net_pnl_usd=net, execution_cost_usd=execution_cost, close_commission_usd=close_commission, balance_before=balance_before, balance_after=self.balance)
        self.cycle = None

    def result(self, start: date, end: date) -> dict[str, Any]:
        closes = [event for event in self.events if event["kind"] == "CLOSE"]
        return {
            "artifact_kind": "MECHANICAL_BOT_MONTHLY_BACKTEST",
            "policy": {"diagnostic_only": True, "can_trade": False, "entry_authorized": False, "promotion_authorized": False},
            "symbol": self.config.symbol,
            "period": {"start": str(start), "end": str(end)},
            "config": asdict(self.config),
            "context_lookback_bars": CONTEXT_LOOKBACK_BARS,
            "summary": {"starting_balance": self.config.starting_balance, "ending_balance": self.balance, "net_pnl_usd": self.balance - self.config.starting_balance, "cycles_closed": len(closes), "take_profit_cycles": sum(c["reason"] == "take_profit_aggregate" for c in closes), "loss_cycles": sum(c["reason"] == "max_floating_loss" for c in closes), "max_drawdown_usd": self.max_drawdown_usd, "max_drawdown_pct": (self.max_drawdown_usd / self.peak_equity * 100.0) if self.peak_equity else 0.0},
            "events": self.events,
        }


def parquet_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {str(path): sha256(path.read_bytes()).hexdigest() for path in paths}


def write_events_jsonl(events: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def load_parquet_frames(directory: Path, symbol: str = "EURUSD") -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Load the five required local parquet feeds and return their SHA-256 lineage."""
    paths = {tf: directory / f"{symbol}_{tf}.parquet" for tf in ("D1", "H4", "H1", "M15", "M1")}
    absent = [str(path) for path in paths.values() if not path.is_file()]
    if absent:
        raise FileNotFoundError(f"missing required parquet feeds: {absent}")
    return {tf: pd.read_parquet(path) for tf, path in paths.items()}, parquet_hashes(paths.values())


def run_month_from_parquets(
    directory: Path,
    start: date,
    end: date,
    *,
    config: MonthlyBotConfig = MonthlyBotConfig(),
    events_path: Path | None = None,
    progress: Callable[[date, int, int], None] | None = None,
) -> dict[str, Any]:
    """Convenience public API used by a report runner; never connects to MT5."""
    frames, hashes = load_parquet_frames(directory, config.symbol)
    replay = MonthlyMechanicalBacktest(frames, config)
    result = replay.run(start, end, progress=progress)
    result["input_sha256"] = hashes
    if events_path is not None:
        write_events_jsonl(result["events"], events_path)
        result["events_jsonl"] = str(events_path)
    return result
