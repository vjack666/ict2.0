"""Grafo de navegación multi-timeframe — Context State (no entry).

Implementa la lectura normativa de
``docs/SDD_CONTEXT_STATE_MTF_NAVIGATION.md``:

- HTF produce **restricciones** (location, regime, structure), no gatillos.
- La navegación es un grafo/árbol de preguntas D1 → H4 → H1 → LTF.
- Solo velas HTF **cerradas** respecto del timestamp de decisión (EXEC).
- **No** emite señales de compra/venta ni PnL.
- **No** usa EMA como bias normativo.

Uso típico::

    nav = MTFNavigator({"D1": df_d1, "H4": df_h4, "H1": df_h1})
    state = nav.navigate(decision_time=ts, exec_tf="H1")
    # state.constraints / state.path / state.allowed_questions
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import bisect

from detectors.bos import BosConfig, detect_bos
from tools.displacement import DisplacementConfig, detect_displacement

try:
    from engine.sequential_events import SequentialChain, Stage as SeqStage, run_sequential, SeqConfig
except ImportError:  # pragma: no cover
    SequentialChain = None  # type: ignore
    SeqStage = None  # type: ignore
    run_sequential = None  # type: ignore
    SeqConfig = None  # type: ignore


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

class TimeframeLayer(str, Enum):
    D1 = "D1"
    H4 = "H4"
    H1 = "H1"
    M15 = "M15"
    M5 = "M5"


# Default hierarchy for navigation (highest context → execution)
DEFAULT_HIERARCHY: tuple[TimeframeLayer, ...] = (
    TimeframeLayer.D1,
    TimeframeLayer.H4,
    TimeframeLayer.H1,
    TimeframeLayer.M15,
    TimeframeLayer.M5,
)


class NavQuestion(str, Enum):
    """Preguntas que el grafo puede resolver en cada capa."""

    HAS_RELEVANT_CONTEXT = "HAS_RELEVANT_CONTEXT"  # D1
    WHERE_IN_CONTEXT = "WHERE_IN_CONTEXT"  # H4
    HAS_STRUCTURE = "HAS_STRUCTURE"  # H1
    HAS_SEQUENCE_DEPTH = "HAS_SEQUENCE_DEPTH"  # H1
    HAS_TRIGGER = "HAS_TRIGGER"  # LTF
    WAITING_RETEST = "WAITING_RETEST"  # LTF


class RegimeLabel(str, Enum):
    TREND_BULL = "TREND_BULL"
    TREND_BEAR = "TREND_BEAR"
    RANGE = "RANGE"
    EXPANSION = "EXPANSION"
    RETRACEMENT = "RETRACEMENT"
    COMPRESSION = "COMPRESSION"
    UNKNOWN = "UNKNOWN"


class StructureBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Zone:
    low: float
    high: float
    kind: str = "POI"  # POI | BSL | SSL | DEALING
    bar_index: int | None = None
    detail: str = ""

    @property
    def mid(self) -> float:
        return 0.5 * (self.low + self.high)

    def contains(self, price: float) -> bool:
        return self.low <= price <= self.high

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LayerSnapshot:
    """Estado point-in-time de una temporalidad (solo velas cerradas)."""

    layer: TimeframeLayer
    asof_bar: int
    asof_time: Any
    last_close: float
    structure_bias: StructureBias = StructureBias.UNKNOWN
    regime: RegimeLabel = RegimeLabel.UNKNOWN
    zones: list[Zone] = field(default_factory=list)
    last_bos_direction: int | None = None  # +1 / -1
    last_bos_bar: int | None = None
    displacement_recent: bool = False
    range_high: float | None = None
    range_low: float | None = None
    answers: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer.value,
            "asof_bar": self.asof_bar,
            "asof_time": str(self.asof_time),
            "last_close": self.last_close,
            "structure_bias": self.structure_bias.value,
            "regime": self.regime.value,
            "zones": [z.to_dict() for z in self.zones],
            "last_bos_direction": self.last_bos_direction,
            "last_bos_bar": self.last_bos_bar,
            "displacement_recent": self.displacement_recent,
            "range_high": self.range_high,
            "range_low": self.range_low,
            "answers": self.answers,
            "notes": list(self.notes),
        }


@dataclass
class ContextConstraints:
    """Mapa de restricciones emitido por el grafo (no es señal)."""

    decision_time: Any
    exec_tf: str
    direction_hint: StructureBias = StructureBias.UNKNOWN
    location_zones: list[Zone] = field(default_factory=list)
    liquidity_targets: list[Zone] = field(default_factory=list)
    regime_stack: dict[str, str] = field(default_factory=dict)
    allow_long: bool | None = None  # None = no opinion
    allow_short: bool | None = None
    sequence_required: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_time": str(self.decision_time),
            "exec_tf": self.exec_tf,
            "direction_hint": self.direction_hint.value,
            "location_zones": [z.to_dict() for z in self.location_zones],
            "liquidity_targets": [z.to_dict() for z in self.liquidity_targets],
            "regime_stack": dict(self.regime_stack),
            "allow_long": self.allow_long,
            "allow_short": self.allow_short,
            "sequence_required": self.sequence_required,
            "notes": list(self.notes),
            "policy": "CONTEXT_ONLY_NOT_ENTRY",
        }


@dataclass
class NavigationPath:
    """Camino recorrido en el grafo (auditoría)."""

    steps: list[dict[str, Any]] = field(default_factory=list)

    def add(self, layer: TimeframeLayer, question: NavQuestion, answer: Any, detail: str = "") -> None:
        self.steps.append(
            {
                "layer": layer.value,
                "question": question.value,
                "answer": answer,
                "detail": detail,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {"steps": list(self.steps)}


@dataclass
class MarketState:
    """Estado multinivel completo en un decision_time."""

    decision_time: Any
    exec_tf: str
    layers: dict[str, LayerSnapshot] = field(default_factory=dict)
    constraints: ContextConstraints | None = None
    path: NavigationPath = field(default_factory=NavigationPath)
    status: str = "OK"  # OK | INCOMPLETE | BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_time": str(self.decision_time),
            "exec_tf": self.exec_tf,
            "status": self.status,
            "layers": {k: v.to_dict() for k, v in self.layers.items()},
            "constraints": self.constraints.to_dict() if self.constraints else None,
            "path": self.path.to_dict(),
            "policy": "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
        }


# ---------------------------------------------------------------------------
# Geometry helpers (causal, no EMA)
# ---------------------------------------------------------------------------

def _ensure_time(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "time" not in out.columns:
        out["time"] = np.arange(len(out))
    out["time"] = pd.to_datetime(out["time"], utc=False, errors="coerce")
    if out["time"].isna().all():
        out["time"] = pd.to_datetime(np.arange(len(out)), unit="s")
    return out.sort_values("time").reset_index(drop=True)


def _asof_index(df: pd.DataFrame, decision_time: Any) -> int | None:
    """Última barra con time <= decision_time (vela cerrada disponible)."""
    if df.empty:
        return None
    # El feed local suele traer UTC-naive y MT5 puede entregar timestamps
    # explícitamente UTC. Comparar ambos sin normalizar rompe el gate PIT.
    ts = pd.to_datetime(decision_time, utc=True, errors="coerce")
    times = pd.to_datetime(df["time"], utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    # exclusive of future
    mask = times <= ts
    if not mask.any():
        return None
    return int(np.where(mask)[0][-1])


def _causal_swings(high: np.ndarray, low: np.ndarray, left: int = 3) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    n = len(high)
    sh, sl = [], []
    for conf in range(left * 2, n):
        j = conf - left
        if j < left:
            continue
        if high[j] >= high[j - left : j + left + 1].max():
            sh.append((j, float(high[j])))
        if low[j] <= low[j - left : j + left + 1].min():
            sl.append((j, float(low[j])))
    return sh, sl


def _structure_bias_from_swings(
    sh: list[tuple[int, float]], sl: list[tuple[int, float]], upto: int
) -> StructureBias:
    sh_u = [(b, p) for b, p in sh if b <= upto]
    sl_u = [(b, p) for b, p in sl if b <= upto]
    if len(sh_u) < 2 or len(sl_u) < 2:
        return StructureBias.UNKNOWN
    hh = sh_u[-1][1] > sh_u[-2][1]
    hl = sl_u[-1][1] > sl_u[-2][1]
    lh = sh_u[-1][1] < sh_u[-2][1]
    ll = sl_u[-1][1] < sl_u[-2][1]
    if hh and hl:
        return StructureBias.BULLISH
    if lh and ll:
        return StructureBias.BEARISH
    return StructureBias.MIXED


def _dealing_range(high: np.ndarray, low: np.ndarray, upto: int, lookback: int = 50) -> tuple[float, float]:
    a = max(0, upto - lookback + 1)
    return float(high[a : upto + 1].max()), float(low[a : upto + 1].min())


def _eq_pools(
    swings: list[tuple[int, float]],
    high: np.ndarray,
    low: np.ndarray,
    upto: int,
    *,
    is_high: bool,
    min_touches: int = 2,
    tol_mult: float = 0.25,
) -> list[Zone]:
    seg = [(b, p) for b, p in swings if b <= upto]
    if len(seg) < min_touches:
        return []
    zones: list[Zone] = []
    used: set[int] = set()
    for i, (bi, pi) in enumerate(seg):
        if i in used:
            continue
        rng = float(np.mean(high[max(0, bi - 14) : bi + 1] - low[max(0, bi - 14) : bi + 1]))
        tol = max(rng * tol_mult, 1e-9)
        group = [(bi, pi)]
        idxs = [i]
        for j in range(i + 1, len(seg)):
            if abs(seg[j][1] - pi) <= tol:
                group.append(seg[j])
                idxs.append(j)
        if len(group) >= min_touches:
            for j in idxs:
                used.add(j)
            prices = [g[1] for g in group]
            zones.append(
                Zone(
                    low=float(min(prices)),
                    high=float(max(prices)),
                    kind="BSL" if is_high else "SSL",
                    bar_index=int(max(g[0] for g in group)),
                    detail="EQH" if is_high else "EQL",
                )
            )
    return zones


def _regime_from_structure(
    bias: StructureBias, range_high: float, range_low: float, close: float
) -> RegimeLabel:
    if range_high is None or range_low is None or range_high <= range_low:
        return RegimeLabel.UNKNOWN
    pos = (close - range_low) / (range_high - range_low)
    if bias is StructureBias.BULLISH:
        return RegimeLabel.TREND_BULL if pos > 0.35 else RegimeLabel.RETRACEMENT
    if bias is StructureBias.BEARISH:
        return RegimeLabel.TREND_BEAR if pos < 0.65 else RegimeLabel.RETRACEMENT
    if 0.35 <= pos <= 0.65:
        return RegimeLabel.RANGE
    return RegimeLabel.COMPRESSION


# ---------------------------------------------------------------------------
# Navigator
# ---------------------------------------------------------------------------

@dataclass
class NavigatorConfig:
    swing_left: int = 3
    dealing_lookback: int = 50
    bos_lookback: int = 5
    displacement_lookback: int = 8
    hierarchy: tuple[TimeframeLayer, ...] = DEFAULT_HIERARCHY
    # Minimum layers required for status OK
    required_layers: tuple[TimeframeLayer, ...] = (
        TimeframeLayer.D1,
        TimeframeLayer.H4,
        TimeframeLayer.H1,
    )
    # When True, MTFNavigator runs sequential engine on H1 once and indexes by bar
    precompute_sequences: bool = True
    sequence_tf: str = "H1"
    seq_config: Any = None  # optional SeqConfig


class MTFNavigator:
    """Grafo de navegación Context State.

    Parameters
    ----------
    frames:
        Mapping TF name → OHLC DataFrame with columns open/high/low/close/time.
    """

    def __init__(
        self,
        frames: Mapping[str, pd.DataFrame],
        config: NavigatorConfig | None = None,
    ) -> None:
        self.config = config or NavigatorConfig()
        self._frames: dict[str, pd.DataFrame] = {}
        for key, df in frames.items():
            k = key.upper()
            need = {"open", "high", "low", "close"}
            if missing := need - set(df.columns):
                raise KeyError(f"{k}: faltan columnas {missing}")
            self._frames[k] = _ensure_time(df)

        # bar -> max sequence depth of chains whose last_bar <= bar (point-in-time)
        self._seq_depth_by_bar: dict[int, int] = {}
        self._seq_complete_by_bar: dict[int, int] = {}
        self._seq_chains: list[Any] = []
        self._pre: dict[str, dict[str, Any]] = {}
        if self.config.precompute_sequences and run_sequential is not None:
            self._build_sequence_index()
        # Precompute por capa (swings/BOS/displacement/dealing) UNA vez -> navigate O(1)
        self._precompute_layers()

    def available_layers(self) -> list[str]:
        return sorted(self._frames.keys())

    def _precompute_layers(self) -> None:
        """Precompute swings/BOS/displacement/dealing por capa UNA vez (O(n) por capa).

        Los detectores (detect_bos, detect_displacement) son causales (shift/rolling/
        ffill sobre prefix), por lo que el array por barra ya contiene la dirección
        calculada usando solo datos <= j. Lookup en navigate es O(1)/O(log n).
        """
        for k, df in self._frames.items():
            if df.empty:
                self._pre[k] = {}
                continue
            high = df["high"].to_numpy(float)
            low = df["low"].to_numpy(float)
            close = df["close"].to_numpy(float)
            n = len(df)
            sh, sl = _causal_swings(high, low, self.config.swing_left)
            # barras de swings para bisect
            sh_b = [b for b, _ in sh]
            sl_b = [b for b, _ in sl]
            # BOS causal por barra (detect_bos ya es vectorizado causal)
            bos_dir = np.zeros(n, dtype="int64")
            last_bos_dir = np.zeros(n, dtype="int64")
            last_bos_bar = np.zeros(n, dtype="int64")
            try:
                bos = detect_bos(df, BosConfig(swing_lookback=self.config.bos_lookback))
                d = bos["bos_direction"].to_numpy().astype("int64")
                bos_dir[: len(d)] = d[:n]
                # prefijo: ultimo !=0 hasta cada barra
                for j in range(n):
                    if bos_dir[j] != 0:
                        last_bos_dir[j] = bos_dir[j]
                        last_bos_bar[j] = j
                    elif j > 0:
                        last_bos_dir[j] = last_bos_dir[j - 1]
                        last_bos_bar[j] = last_bos_bar[j - 1]
            except Exception:
                pass
            # displacement reciente por barra (rolling lookback)
            disp_recent = np.zeros(n, dtype=bool)
            try:
                ddf = detect_displacement(df, DisplacementConfig())
                db = ddf["displacement_bullish"].to_numpy().astype(bool)
                dbr = ddf["displacement_bearish"].to_numpy().astype(bool)
                lb = self.config.displacement_lookback
                for j in range(n):
                    a = max(0, j - lb + 1)
                    if db[a : j + 1].any() or dbr[a : j + 1].any():
                        disp_recent[j] = True
            except Exception:
                pass
            # dealing range rolling
            lb = self.config.dealing_lookback
            dh = pd.Series(high).rolling(lb, min_periods=1).max().to_numpy()
            dl = pd.Series(low).rolling(lb, min_periods=1).min().to_numpy()
            self._pre[k] = {
                "high": high,
                "low": low,
                "close": close,
                "sh": sh,
                "sl": sl,
                "sh_b": sh_b,
                "sl_b": sl_b,
                "last_bos_dir": last_bos_dir,
                "last_bos_bar": last_bos_bar,
                "disp_recent": disp_recent,
                "dh": dh,
                "dl": dl,
                "n": n,
            }

    def _snapshot(self, layer: TimeframeLayer, decision_time: Any) -> LayerSnapshot | None:
        df = self._frames.get(layer.value)
        if df is None or df.empty:
            return None
        i = _asof_index(df, decision_time)
        if i is None:
            return None
        pre = self._pre.get(layer.value, {})
        if not pre:
            return None
        high = pre["high"]
        low = pre["low"]
        close = pre["close"]
        sh_b = pre["sh_b"]
        sl_b = pre["sl_b"]
        # swings <= i (bisect O(log n))
        si = bisect.bisect_right(sh_b, i)
        sj = bisect.bisect_right(sl_b, i)
        sh_u = pre["sh"][:si]
        sl_u = pre["sl"][:sj]
        bias = _structure_bias_from_swings(sh_u, sl_u, i)
        rh = float(pre["dh"][i])
        rl = float(pre["dl"][i])
        regime = _regime_from_structure(bias, rh, rl, float(close[i]))

        zones: list[Zone] = []
        # eq zones: igual que motor original (swings filtrados <= i, O(swings^2) trivial)
        zones.extend(_eq_pools(sh_u, high, low, i, is_high=True))
        zones.extend(_eq_pools(sl_u, high, low, i, is_high=False))
        zones.append(Zone(low=rl, high=rh, kind="DEALING", bar_index=i, detail="dealing_range"))

        last_bos_dir = int(pre["last_bos_dir"][i]) if pre["last_bos_dir"][i] != 0 else None
        last_bos_bar = int(pre["last_bos_bar"][i]) if pre["last_bos_dir"][i] != 0 else None
        disp_recent = bool(pre["disp_recent"][i])

        snap = LayerSnapshot(
            layer=layer,
            asof_bar=i,
            asof_time=df["time"].iloc[i],
            last_close=float(close[i]),
            structure_bias=bias,
            regime=regime,
            zones=zones,
            last_bos_direction=last_bos_dir,
            last_bos_bar=last_bos_bar,
            displacement_recent=disp_recent,
            range_high=rh,
            range_low=rl,
            notes=[],
        )
        return snap

    def _answer_d1(self, snap: LayerSnapshot, path: NavigationPath) -> bool:
        # Relevant context: known structure or at least dealing range + a liquidity pool
        has_liq = any(z.kind in ("BSL", "SSL") for z in snap.zones)
        has_struct = snap.structure_bias is not StructureBias.UNKNOWN
        ok = has_struct or has_liq
        snap.answers[NavQuestion.HAS_RELEVANT_CONTEXT.value] = ok
        path.add(
            TimeframeLayer.D1,
            NavQuestion.HAS_RELEVANT_CONTEXT,
            ok,
            detail=f"bias={snap.structure_bias.value}, liq_pools={has_liq}",
        )
        return ok

    def _answer_h4(self, snap: LayerSnapshot, d1: LayerSnapshot | None, path: NavigationPath) -> str:
        price = snap.last_close
        loc = "OUTSIDE"
        if d1 and d1.range_low is not None and d1.range_high is not None:
            if d1.range_low <= price <= d1.range_high:
                # position in D1 dealing range
                span = d1.range_high - d1.range_low
                pos = (price - d1.range_low) / span if span > 0 else 0.5
                if pos < 0.33:
                    loc = "DISCOUNT"
                elif pos > 0.67:
                    loc = "PREMIUM"
                else:
                    loc = "EQUILIBRIUM"
        # near D1 liquidity?
        near = []
        if d1:
            for z in d1.zones:
                if z.kind in ("BSL", "SSL", "POI") and (
                    abs(price - z.mid) <= max(z.high - z.low, 1e-6) * 2
                ):
                    near.append(z.detail or z.kind)
        snap.answers[NavQuestion.WHERE_IN_CONTEXT.value] = {
            "location": loc,
            "near_d1_zones": near,
            "h4_bias": snap.structure_bias.value,
        }
        path.add(
            TimeframeLayer.H4,
            NavQuestion.WHERE_IN_CONTEXT,
            loc,
            detail=f"near={near}, h4_bias={snap.structure_bias.value}",
        )
        return loc

    def _answer_h1(self, snap: LayerSnapshot, path: NavigationPath) -> dict[str, Any]:
        has_struct = snap.structure_bias is not StructureBias.UNKNOWN or snap.last_bos_direction is not None
        snap.answers[NavQuestion.HAS_STRUCTURE.value] = has_struct
        path.add(
            TimeframeLayer.H1,
            NavQuestion.HAS_STRUCTURE,
            has_struct,
            detail=f"bias={snap.structure_bias.value}, bos={snap.last_bos_direction}",
        )
        # Sequence depth: prefer sequential engine index (point-in-time); else proxy
        seq_depth = self.sequence_depth_at(snap.asof_bar)
        seq_complete_n = self.sequence_complete_count_at(snap.asof_bar)
        if seq_depth > 0 or self._seq_chains:
            depth_val = seq_depth
            detail = f"sequential_engine max_depth_visible={seq_depth}, complete_chains_seen={seq_complete_n}"
            source = "sequential_events"
        else:
            depth_val = int(has_struct) + int(snap.displacement_recent)
            detail = "proxy=structure+displacement (sequential index empty)"
            source = "proxy"
        snap.answers[NavQuestion.HAS_SEQUENCE_DEPTH.value] = {
            "depth": depth_val,
            "complete_chains_seen": seq_complete_n,
            "source": source,
        }
        path.add(
            TimeframeLayer.H1,
            NavQuestion.HAS_SEQUENCE_DEPTH,
            depth_val,
            detail=detail,
        )
        return {
            "has_structure": has_struct,
            "depth": depth_val,
            "complete_chains_seen": seq_complete_n,
            "source": source,
        }

    def _answer_ltf(self, snap: LayerSnapshot, path: NavigationPath) -> dict[str, Any]:
        # Trigger proxy: recent displacement; retest unknown without zone tracking
        has_trigger = snap.displacement_recent
        snap.answers[NavQuestion.HAS_TRIGGER.value] = has_trigger
        snap.answers[NavQuestion.WAITING_RETEST.value] = None  # requires active FVG zone feed
        path.add(
            snap.layer,
            NavQuestion.HAS_TRIGGER,
            has_trigger,
            detail="proxy=recent_displacement",
        )
        path.add(
            snap.layer,
            NavQuestion.WAITING_RETEST,
            None,
            detail="not_resolved_without_active_fvg_feed",
        )
        return {"has_trigger": has_trigger, "waiting_retest": None}

    def _build_constraints(
        self,
        decision_time: Any,
        exec_tf: str,
        layers: dict[str, LayerSnapshot],
    ) -> ContextConstraints:
        d1 = layers.get("D1")
        h4 = layers.get("H4")
        h1 = layers.get("H1")

        direction = StructureBias.UNKNOWN
        if d1 and d1.structure_bias in (StructureBias.BULLISH, StructureBias.BEARISH):
            direction = d1.structure_bias
        elif h4 and h4.structure_bias in (StructureBias.BULLISH, StructureBias.BEARISH):
            direction = h4.structure_bias

        location_zones: list[Zone] = []
        liquidity_targets: list[Zone] = []
        if d1:
            for z in d1.zones:
                if z.kind in ("BSL", "SSL"):
                    liquidity_targets.append(z)
                if z.kind in ("DEALING", "POI"):
                    location_zones.append(z)

        regime_stack = {
            k: v.regime.value for k, v in layers.items()
        }

        allow_long: bool | None = None
        allow_short: bool | None = None
        notes: list[str] = [
            "Constraints only — NOT an entry signal",
            "EMA is not used as normative HTF bias",
        ]
        if direction is StructureBias.BULLISH:
            allow_long = True
            allow_short = False
            notes.append("direction_hint from structure (D1 preferred)")
        elif direction is StructureBias.BEARISH:
            allow_long = False
            allow_short = True
            notes.append("direction_hint from structure (D1 preferred)")
        else:
            notes.append("no firm direction_hint — both sides unconstrained by bias")

        # Location: if H4 said DISCOUNT and bullish, location supports longs more
        if h4:
            loc = (h4.answers.get(NavQuestion.WHERE_IN_CONTEXT.value) or {})
            if isinstance(loc, dict):
                loc = loc.get("location")
            if direction is StructureBias.BULLISH and loc == "PREMIUM":
                notes.append("bullish bias but price in PREMIUM of D1 range — location weaker for longs")
            if direction is StructureBias.BEARISH and loc == "DISCOUNT":
                notes.append("bearish bias but price in DISCOUNT of D1 range — location weaker for shorts")

        return ContextConstraints(
            decision_time=decision_time,
            exec_tf=exec_tf,
            direction_hint=direction,
            location_zones=location_zones,
            liquidity_targets=liquidity_targets,
            regime_stack=regime_stack,
            allow_long=allow_long,
            allow_short=allow_short,
            sequence_required=True,
            notes=notes,
        )


    def _build_sequence_index(self) -> None:
        """Run sequential engine on sequence_tf; index max depth visible at each bar.

        Anti-look-ahead: a chain only contributes to bar i if chain.last_bar <= i.
        """
        tf = self.config.sequence_tf.upper()
        df = self._frames.get(tf)
        if df is None or df.empty or run_sequential is None:
            return
        cfg = self.config.seq_config
        if cfg is None and SeqConfig is not None:
            cfg = SeqConfig(structure_mode="canonical_bos", max_active_chains=128)
        chains = run_sequential(df, cfg, symbol="", timeframe=tf)
        self._seq_chains = chains
        n = len(df)
        ends = sorted(
            (
                (int(ch.last_bar), len(ch.nodes), 1 if ch.status == "COMPLETE" else 0)
                for ch in chains
                if 0 <= int(ch.last_bar) < n
            ),
            key=lambda x: x[0],
        )
        j = 0
        max_d = 0
        n_complete = 0
        for i in range(n):
            while j < len(ends) and ends[j][0] <= i:
                max_d = max(max_d, ends[j][1])
                n_complete += ends[j][2]
                j += 1
            self._seq_depth_by_bar[i] = max_d
            self._seq_complete_by_bar[i] = n_complete

    def sequence_depth_at(self, bar_index: int) -> int:
        return int(self._seq_depth_by_bar.get(bar_index, 0))

    def sequence_complete_count_at(self, bar_index: int) -> int:
        return int(self._seq_complete_by_bar.get(bar_index, 0))

    def navigate(
        self,
        decision_time: Any,
        exec_tf: str = "H1",
        stop_if_no_d1_context: bool = False,
    ) -> MarketState:
        """Recorre el grafo D1→…→exec y devuelve MarketState + constraints.

        Never returns an entry order.
        """
        path = NavigationPath()
        layers: dict[str, LayerSnapshot] = {}
        exec_layer = TimeframeLayer[exec_tf.upper()] if exec_tf.upper() in TimeframeLayer.__members__ else TimeframeLayer.H1

        # Walk hierarchy until exec layer (inclusive)
        walk: list[TimeframeLayer] = []
        for lyr in self.config.hierarchy:
            walk.append(lyr)
            if lyr == exec_layer:
                break

        d1_snap: LayerSnapshot | None = None
        for lyr in walk:
            snap = self._snapshot(lyr, decision_time)
            if snap is None:
                path.add(lyr, NavQuestion.HAS_RELEVANT_CONTEXT, False, detail="no_data_or_no_closed_bar")
                continue
            layers[lyr.value] = snap

            if lyr is TimeframeLayer.D1:
                ok = self._answer_d1(snap, path)
                d1_snap = snap
                if stop_if_no_d1_context and not ok:
                    state = MarketState(
                        decision_time=decision_time,
                        exec_tf=exec_tf.upper(),
                        layers=layers,
                        path=path,
                        status="INCOMPLETE",
                    )
                    state.constraints = self._build_constraints(decision_time, exec_tf.upper(), layers)
                    state.constraints.notes.append("stopped: no D1 relevant context")
                    return state

            elif lyr is TimeframeLayer.H4:
                self._answer_h4(snap, d1_snap, path)

            elif lyr is TimeframeLayer.H1:
                self._answer_h1(snap, path)

            else:
                # M15 / M5
                self._answer_ltf(snap, path)

        missing = [L.value for L in self.config.required_layers if L.value not in layers]
        status = "OK" if not missing else "INCOMPLETE"
        state = MarketState(
            decision_time=decision_time,
            exec_tf=exec_tf.upper(),
            layers=layers,
            path=path,
            status=status,
        )
        state.constraints = self._build_constraints(decision_time, exec_tf.upper(), layers)
        if missing:
            state.constraints.notes.append(f"missing_layers={missing}")
        return state

    def navigate_series(
        self,
        decision_times: Sequence[Any],
        exec_tf: str = "H1",
    ) -> list[MarketState]:
        return [self.navigate(t, exec_tf=exec_tf) for t in decision_times]
