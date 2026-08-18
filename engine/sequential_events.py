"""Motor de eventos secuenciales ICT (no co-ocurrencia de flags).

Cadena canónica (orden temporal estricto, point-in-time):

    LIQUIDITY_POOL (EQH/EQL)
      → SWEEP
      → DISPLACEMENT
      → STRUCTURE (BOS-lite)
      → OB
      → FVG
      → RETEST

Cada eslabón solo puede activarse en una barra **estrictamente posterior**
(o, donde el detector lo permita, en la misma secuencia causal documentada)
al eslabón anterior. No se acepta "todos los flags true en la misma vela"
como sustituto de la secuencia.

Este módulo:
- no emite entradas ni PnL;
- no usa ATR/EMA como sesgo;
- produce cadenas auditables con lineage de barras.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.relations import relate_fvg_ob
from tools.displacement import detect_displacement, DisplacementConfig


class Stage(str, Enum):
    LIQUIDITY_POOL = "LIQUIDITY_POOL"
    SWEEP = "SWEEP"
    DISPLACEMENT = "DISPLACEMENT"
    STRUCTURE = "STRUCTURE"
    OB = "OB"
    FVG = "FVG"
    RETEST = "RETEST"


STAGE_ORDER: tuple[Stage, ...] = (
    Stage.LIQUIDITY_POOL,
    Stage.SWEEP,
    Stage.DISPLACEMENT,
    Stage.STRUCTURE,
    Stage.OB,
    Stage.FVG,
    Stage.RETEST,
)


@dataclass(frozen=True)
class SeqConfig:
    """Ventanas y umbrales del motor secuencial."""

    swing_left: int = 3
    eq_tolerance_range_mult: float = 0.25  # tol = mult * avg(high-low, 14)
    min_eq_touches: int = 2
    max_bars_pool_to_sweep: int = 40
    max_bars_sweep_to_disp: int = 8
    max_bars_disp_to_struct: int = 12
    max_bars_struct_to_ob: int = 8
    max_bars_ob_to_fvg: int = 20
    max_bars_fvg_to_retest: int = 48
    displacement: DisplacementConfig = field(default_factory=DisplacementConfig)
    require_ob_fvg_causal: bool = True
    max_active_chains: int = 64


@dataclass
class SeqNode:
    stage: Stage
    bar: int
    direction: int  # +1 bullish narrative (SSL sweep → up), -1 bearish
    level: float | None = None
    object_id: str = ""
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["stage"] = self.stage.value
        return d


@dataclass
class SequentialChain:
    """Una cadena parcial o completa de eventos ordenados."""

    chain_id: str
    direction: int
    nodes: list[SeqNode] = field(default_factory=list)
    status: str = "OPEN"  # OPEN | COMPLETE | EXPIRED
    created_bar: int = 0
    last_bar: int = 0

    @property
    def stages_present(self) -> list[str]:
        return [n.stage.value for n in self.nodes]

    @property
    def is_complete(self) -> bool:
        return self.status == "COMPLETE" or (
            len(self.nodes) == len(STAGE_ORDER)
            and all(n.stage == STAGE_ORDER[i] for i, n in enumerate(self.nodes))
        )

    def stage_bar(self, stage: Stage) -> int | None:
        for n in self.nodes:
            if n.stage is stage:
                return n.bar
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "direction": self.direction,
            "status": self.status,
            "created_bar": self.created_bar,
            "last_bar": self.last_bar,
            "stages": self.stages_present,
            "nodes": [n.to_dict() for n in self.nodes],
        }


def _avg_range(high: np.ndarray, low: np.ndarray, i: int, period: int = 14) -> float:
    a = max(0, i - period + 1)
    seg = high[a : i + 1] - low[a : i + 1]
    if len(seg) == 0:
        return 1e-9
    return float(max(np.mean(seg), 1e-9))


def _causal_swings(
    high: np.ndarray, low: np.ndarray, left: int
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Pivots confirmados solo con velas a la derecha ya cerradas (sin center)."""
    n = len(high)
    sh: list[tuple[int, float]] = []
    sl: list[tuple[int, float]] = []
    # Pivot at j confirmed at j+left when j+left is known
    for conf in range(left * 2, n):
        j = conf - left
        if j < left:
            continue
        w_h = high[j - left : j + left + 1]
        w_l = low[j - left : j + left + 1]
        if high[j] >= w_h.max():
            sh.append((j, float(high[j])))
        if low[j] <= w_l.min():
            sl.append((j, float(low[j])))
    return sh, sl


def _build_eq_pools(
    swings: list[tuple[int, float]],
    high: np.ndarray,
    low: np.ndarray,
    *,
    is_high: bool,
    tol_mult: float,
    min_touches: int,
) -> list[dict[str, Any]]:
    """Clusters EQH/EQL: ≥ min_touches swings within tolerance."""
    if len(swings) < min_touches:
        return []
    pools: list[dict[str, Any]] = []
    used = set()
    for i, (bi, pi) in enumerate(swings):
        if i in used:
            continue
        tol = _avg_range(high, low, bi) * tol_mult
        group = [(bi, pi)]
        idxs = [i]
        for j in range(i + 1, len(swings)):
            bj, pj = swings[j]
            if abs(pj - pi) <= tol:
                group.append((bj, pj))
                idxs.append(j)
        if len(group) >= min_touches:
            for j in idxs:
                used.add(j)
            bars = [g[0] for g in group]
            prices = [g[1] for g in group]
            pools.append(
                {
                    "kind": "EQH" if is_high else "EQL",
                    "direction_target": -1 if is_high else 1,  # sweep EQH → bearish narrative
                    "level": float(np.mean(prices)),
                    "top": float(max(prices)),
                    "bot": float(min(prices)),
                    "form_bar": int(max(bars)),  # pool known after last touch confirmed
                    "touch_bars": bars,
                }
            )
    return pools


@dataclass
class _Atomic:
    """Eventos atómicos indexados por barra para avance de cadenas."""

    # bar -> list
    sweeps: dict[int, list[dict[str, Any]]]
    displ: dict[int, list[dict[str, Any]]]
    structs: dict[int, list[dict[str, Any]]]
    obs: dict[int, list[Any]]
    fvgs: dict[int, list[Any]]
    # precomputed objects for relation
    all_obs: list[Any]
    all_fvgs: list[Any]


def _detect_atomics(df: pd.DataFrame, cfg: SeqConfig) -> _Atomic:
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    close = df["close"].to_numpy(float)
    n = len(df)

    sh, sl = _causal_swings(high, low, cfg.swing_left)
    eqh = _build_eq_pools(
        sh, high, low, is_high=True, tol_mult=cfg.eq_tolerance_range_mult, min_touches=cfg.min_eq_touches
    )
    eql = _build_eq_pools(
        sl, high, low, is_high=False, tol_mult=cfg.eq_tolerance_range_mult, min_touches=cfg.min_eq_touches
    )
    pools = eqh + eql

    sweeps: dict[int, list[dict[str, Any]]] = {}
    # Sweep: take pool extreme then close back through level within window after form_bar
    for pool in pools:
        form = pool["form_bar"]
        level = pool["level"]
        top, bot = pool["top"], pool["bot"]
        # bearish narrative: sweep EQH (buy-side) → direction -1
        # bullish: sweep EQL (sell-side) → direction +1
        direction = int(pool["direction_target"])
        for b in range(form + 1, min(n, form + 1 + cfg.max_bars_pool_to_sweep)):
            swept = False
            if direction == -1:
                # pierce above top then close below level
                if high[b] > top and close[b] < level:
                    swept = True
            else:
                if low[b] < bot and close[b] > level:
                    swept = True
            if swept:
                sweeps.setdefault(b, []).append(
                    {
                        "direction": direction,
                        "level": level,
                        "pool_kind": pool["kind"],
                        "pool_form_bar": form,
                        "detail": f"sweep_{pool['kind']}",
                    }
                )
                break  # first sweep of this pool

    # Displacement
    disp_df = detect_displacement(df, cfg.displacement)
    displ: dict[int, list[dict[str, Any]]] = {}
    for i in range(n):
        if bool(disp_df["displacement_bullish"].iloc[i]):
            displ.setdefault(i, []).append({"direction": 1, "detail": "disp_bull"})
        if bool(disp_df["displacement_bearish"].iloc[i]):
            displ.setdefault(i, []).append({"direction": -1, "detail": "disp_bear"})

    # Structure BOS-lite: close beyond last confirmed opposite swing
    structs: dict[int, list[dict[str, Any]]] = {}
    last_sh = np.nan
    last_sl = np.nan
    sh_set = {b: p for b, p in sh}
    sl_set = {b: p for b, p in sl}
    for i in range(n):
        if i in sh_set:
            last_sh = sh_set[i]
        if i in sl_set:
            last_sl = sl_set[i]
        if not np.isnan(last_sh) and close[i] > last_sh:
            structs.setdefault(i, []).append(
                {"direction": 1, "level": float(last_sh), "detail": "bos_up_lite"}
            )
        if not np.isnan(last_sl) and close[i] < last_sl:
            structs.setdefault(i, []).append(
                {"direction": -1, "level": float(last_sl), "detail": "bos_down_lite"}
            )

    # OB / FVG canonical detectors
    # Monotonic numeric times so MarketObject temporal contract sorts correctly
    records = df[["open", "high", "low", "close"]].copy()
    records["time"] = list(range(n))
    row_dicts = records.to_dict("records")
    all_obs = detect_order_blocks(row_dicts, timeframe="SEQ", symbol="")
    all_fvgs = detect_fvg(row_dicts, timeframe="SEQ", symbol="")

    obs_map: dict[int, list[Any]] = {}
    for o in all_obs:
        bi = o.confirmation_bar if o.confirmation_bar is not None else o.bar_index
        if bi is not None:
            obs_map.setdefault(int(bi), []).append(o)
    fvg_map: dict[int, list[Any]] = {}
    for f in all_fvgs:
        bi = f.confirmation_bar if f.confirmation_bar is not None else f.bar_index
        if bi is not None:
            fvg_map.setdefault(int(bi), []).append(f)

    return _Atomic(sweeps, displ, structs, obs_map, fvg_map, all_obs, all_fvgs)


def _next_stage(chain: SequentialChain) -> Stage | None:
    have = {n.stage for n in chain.nodes}
    for s in STAGE_ORDER:
        if s not in have:
            return s
    return None


def _window(cfg: SeqConfig, from_stage: Stage) -> int:
    return {
        Stage.LIQUIDITY_POOL: cfg.max_bars_pool_to_sweep,
        Stage.SWEEP: cfg.max_bars_sweep_to_disp,
        Stage.DISPLACEMENT: cfg.max_bars_disp_to_struct,
        Stage.STRUCTURE: cfg.max_bars_struct_to_ob,
        Stage.OB: cfg.max_bars_ob_to_fvg,
        Stage.FVG: cfg.max_bars_fvg_to_retest,
    }.get(from_stage, 20)


def run_sequential(
    df: pd.DataFrame,
    cfg: SeqConfig | None = None,
    symbol: str = "",
    timeframe: str = "H1",
) -> list[SequentialChain]:
    """Ejecuta el motor secuencial sobre OHLC point-in-time.

    Parameters
    ----------
    df : DataFrame con open/high/low/close y opcionalmente time.
    """
    if cfg is None:
        cfg = SeqConfig()
    need = {"open", "high", "low", "close"}
    missing = need - set(df.columns)
    if missing:
        raise KeyError(f"faltan columnas {missing}")

    work = df.reset_index(drop=True).copy()
    n = len(work)
    high = work["high"].to_numpy(float)
    low = work["low"].to_numpy(float)
    close = work["close"].to_numpy(float)

    atom = _detect_atomics(work, cfg)

    # Seed chains from liquidity pools (EQH/EQL form_bar)
    sh, sl = _causal_swings(high, low, cfg.swing_left)
    pools = _build_eq_pools(
        sh, high, low, is_high=True, tol_mult=cfg.eq_tolerance_range_mult, min_touches=cfg.min_eq_touches
    ) + _build_eq_pools(
        sl, high, low, is_high=False, tol_mult=cfg.eq_tolerance_range_mult, min_touches=cfg.min_eq_touches
    )

    chains: list[SequentialChain] = []
    open_chains: list[SequentialChain] = []
    cid = 0

    def new_chain(pool: dict[str, Any]) -> SequentialChain:
        nonlocal cid
        cid += 1
        direction = int(pool["direction_target"])
        node = SeqNode(
            stage=Stage.LIQUIDITY_POOL,
            bar=int(pool["form_bar"]),
            direction=direction,
            level=float(pool["level"]),
            object_id=f"{pool['kind']}_{pool['form_bar']}",
            detail=pool["kind"],
            extra={"top": pool["top"], "bot": pool["bot"]},
        )
        ch = SequentialChain(
            chain_id=f"SEQ_{timeframe}_{cid}",
            direction=direction,
            nodes=[node],
            status="OPEN",
            created_bar=node.bar,
            last_bar=node.bar,
        )
        return ch

    # Index pools by form bar for seeding when we pass that bar
    pools_by_bar: dict[int, list[dict[str, Any]]] = {}
    for p in pools:
        pools_by_bar.setdefault(int(p["form_bar"]), []).append(p)

    for i in range(n):
        # seed
        for p in pools_by_bar.get(i, []):
            if len(open_chains) >= cfg.max_active_chains:
                break
            open_chains.append(new_chain(p))

        still_open: list[SequentialChain] = []
        for ch in open_chains:
            nxt = _next_stage(ch)
            if nxt is None:
                ch.status = "COMPLETE"
                chains.append(ch)
                continue

            prev = ch.nodes[-1]
            max_lag = _window(cfg, prev.stage)
            # expire if too far
            if i - prev.bar > max_lag and nxt is not Stage.RETEST:
                # allow RETEST window separately
                if nxt != Stage.RETEST:
                    ch.status = "EXPIRED"
                    chains.append(ch)
                    continue
            if nxt == Stage.RETEST and i - prev.bar > cfg.max_bars_fvg_to_retest:
                ch.status = "EXPIRED"
                chains.append(ch)
                continue

            advanced = False
            if nxt is Stage.SWEEP and i > prev.bar:
                for sw in atom.sweeps.get(i, []):
                    if sw["direction"] != ch.direction:
                        continue
                    if sw["pool_form_bar"] > prev.bar:
                        continue  # must sweep the pool already in chain (same or earlier)
                    # prefer matching level proximity
                    if prev.level is not None and abs(sw["level"] - prev.level) > _avg_range(high, low, i):
                        continue
                    ch.nodes.append(
                        SeqNode(
                            Stage.SWEEP,
                            i,
                            ch.direction,
                            sw["level"],
                            object_id=f"SWEEP_{i}",
                            detail=sw["detail"],
                            extra={"pool_form_bar": sw["pool_form_bar"]},
                        )
                    )
                    ch.last_bar = i
                    advanced = True
                    break

            elif nxt is Stage.DISPLACEMENT and i > prev.bar:
                for d in atom.displ.get(i, []):
                    if d["direction"] != ch.direction:
                        continue
                    ch.nodes.append(
                        SeqNode(Stage.DISPLACEMENT, i, ch.direction, None, f"DISP_{i}", d["detail"])
                    )
                    ch.last_bar = i
                    advanced = True
                    break

            elif nxt is Stage.STRUCTURE and i > prev.bar:
                for s in atom.structs.get(i, []):
                    if s["direction"] != ch.direction:
                        continue
                    ch.nodes.append(
                        SeqNode(
                            Stage.STRUCTURE,
                            i,
                            ch.direction,
                            s.get("level"),
                            f"STRUCT_{i}",
                            s["detail"],
                        )
                    )
                    ch.last_bar = i
                    advanced = True
                    break

            elif nxt is Stage.OB and i > prev.bar:
                for o in atom.obs.get(i, []):
                    if int(o.direction) != ch.direction:
                        continue
                    ch.nodes.append(
                        SeqNode(
                            Stage.OB,
                            i,
                            ch.direction,
                            float((o.zone_low + o.zone_high) / 2),
                            o.id,
                            "order_block",
                            extra={"zone_low": o.zone_low, "zone_high": o.zone_high},
                        )
                    )
                    ch.last_bar = i
                    advanced = True
                    break

            elif nxt is Stage.FVG and i > prev.bar:
                for f in atom.fvgs.get(i, []):
                    if int(f.direction) != ch.direction:
                        continue
                    if cfg.require_ob_fvg_causal:
                        ob_node = next((x for x in ch.nodes if x.stage is Stage.OB), None)
                        if ob_node is None:
                            continue
                        # strict: OB bar before FVG confirm
                        if ob_node.bar >= i:
                            continue
                        # optional geometric relation check
                        ob_obj = next((o for o in atom.all_obs if o.id == ob_node.object_id), None)
                        if ob_obj is not None:
                            rel = relate_fvg_ob(
                                [f], [ob_obj], max_bars_apart=cfg.max_bars_ob_to_fvg, causal_mode="strict"
                            )
                            if not rel:
                                # still allow sequential order without overlap (structure path)
                                # keep soft: require only temporal OB before FVG
                                pass
                    ch.nodes.append(
                        SeqNode(
                            Stage.FVG,
                            i,
                            ch.direction,
                            float((f.zone_low + f.zone_high) / 2),
                            f.id,
                            "fvg",
                            extra={"zone_low": f.zone_low, "zone_high": f.zone_high},
                        )
                    )
                    ch.last_bar = i
                    advanced = True
                    break

            elif nxt is Stage.RETEST and i > prev.bar:
                fvg_node = next((x for x in ch.nodes if x.stage is Stage.FVG), None)
                if fvg_node is not None and fvg_node.extra:
                    zlo = float(fvg_node.extra["zone_low"])
                    zhi = float(fvg_node.extra["zone_high"])
                    # retest: price trades back into the zone after FVG bar
                    hit = low[i] <= zhi and high[i] >= zlo
                    if hit:
                        ch.nodes.append(
                            SeqNode(
                                Stage.RETEST,
                                i,
                                ch.direction,
                                float((zlo + zhi) / 2),
                                f"RETEST_{i}",
                                "retest_fvg_zone",
                            )
                        )
                        ch.last_bar = i
                        ch.status = "COMPLETE"
                        advanced = True

            if ch.status == "COMPLETE":
                chains.append(ch)
            else:
                still_open.append(ch)

        open_chains = still_open

    # flush
    for ch in open_chains:
        if ch.status == "OPEN":
            ch.status = "EXPIRED"
        chains.append(ch)

    chains.sort(key=lambda c: (c.created_bar, c.chain_id))
    return chains


def summarize_chains(chains: Sequence[SequentialChain]) -> dict[str, Any]:
    """Conteos por profundidad de cadena y completitud."""
    by_depth: dict[int, int] = {}
    by_status: dict[str, int] = {}
    complete_dirs = {1: 0, -1: 0}
    for c in chains:
        d = len(c.nodes)
        by_depth[d] = by_depth.get(d, 0) + 1
        by_status[c.status] = by_status.get(c.status, 0) + 1
        if c.status == "COMPLETE":
            complete_dirs[c.direction] = complete_dirs.get(c.direction, 0) + 1
    return {
        "n_chains": len(chains),
        "by_depth": {str(k): v for k, v in sorted(by_depth.items())},
        "by_status": by_status,
        "complete_bull": complete_dirs.get(1, 0),
        "complete_bear": complete_dirs.get(-1, 0),
        "stage_order": [s.value for s in STAGE_ORDER],
    }
