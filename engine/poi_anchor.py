"""engine/poi_anchor.py — Ancla narrativa de POI al TF padre (Brecha B, tesis 18).

El POI real esta ANCLADO a la narrativa: un BOS/CHOCH en el TF padre
(D1/H4/H1) en la MISMA direccion del setup LTF (libro 21 §4). Sin eso, el
FVG/OB del LTF es "geometria suelta" (auditoria: 100% de zonas sin ancla).

Contrato (igual filosofia que ict_backtest.poi_anchor, pero del LADO DEL
MOTOR: aqui vive la DECISION de que es un POI anclado; el backtest solo lo
enchufa como htf_poi_fn). CRIT: SIN indicadores. engine/ NUNCA importa
ict_backtest/. Anti look-ahead por timestamp cross-TF (un H4 no comparte
bar_index con un M15).

Uso:
    from engine.poi_anchor import make_htf_poi_fn
    htf_poi_fn = make_htf_poi_fn(ltf_frame, {"D1": d1, "H4": h4, "H1": h1})
    # luego pasar htf_poi_fn a ict_backtest.sequence.run_sequence(...)
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.bos import detect_market_structure
from engine.bias.narrative import BULLISH, BEARISH

# TF que pueden actuar como padre de un POI LTF (ontologia market_object)
_HTF_PARENTS = ("D1", "H4", "H1")

# Direccion del motor -> valor numerico (1 alcista, -1 bajista)
_DIR_NUM = {BULLISH: 1, BEARISH: -1, "BULLISH": 1, "BEARISH": -1}


@dataclass(frozen=True)
class _ParentEvent:
    time: pd.Timestamp
    direction: int  # 1 / -1
    kind: str       # "BOS" / "CHOCH"
    tf: str
    level: float | None = None
    bar_index: int | None = None


def _direction_to_num(direction) -> int:
    if isinstance(direction, (int,)):
        return 1 if direction > 0 else (-1 if direction < 0 else 0)
    return _DIR_NUM.get(str(direction).upper(), 0)


def build_htf_structure_index(
    htf_frames: dict[str, pd.DataFrame],
    parents: tuple[str, ...] = _HTF_PARENTS,
) -> list[_ParentEvent]:
    """Lista plana de eventos BOS/CHOCH en los TF padre, ordenada por time.

    Cada evento lleva su timestamp real para el chequeo anti look-ahead cross-TF.
    """
    events: list[_ParentEvent] = []
    for tf in parents:
        frame = htf_frames.get(tf)
        if frame is None or len(frame) < 3:
            continue
        # time puede venir como columna o como indice
        if "time" in frame.columns:
            times = pd.to_datetime(frame["time"], utc=True).reset_index(drop=True)
        else:
            times = pd.to_datetime(frame.index).reset_index(drop=True)
        try:
            struct = detect_market_structure(frame)
        except Exception:
            continue
        bos = struct.frame["bos_dir"].fillna(0).to_numpy()
        choch = struct.frame["choch_dir"].fillna(0).to_numpy()
        for i in range(len(bos)):
            t = times.iloc[i] if i < len(times) else None
            if bos[i] != 0:
                raw_level = struct.frame["bos_level"].iloc[i] if "bos_level" in struct.frame.columns else None
                level = None if raw_level is None or pd.isna(raw_level) else float(raw_level)
                events.append(_ParentEvent(time=t, direction=int(bos[i]),
                                           kind="BOS", tf=tf, level=level, bar_index=int(i)))
            if choch[i] != 0:
                raw_level = (struct.frame["choch_proj_level"].iloc[i]
                             if "choch_proj_level" in struct.frame.columns else None)
                level = None if raw_level is None or pd.isna(raw_level) else float(raw_level)
                events.append(_ParentEvent(time=t, direction=int(choch[i]),
                                           kind="CHOCH", tf=tf, level=level, bar_index=int(i)))
    # orden estable por tiempo (los sin tiempo van al final, no anclan)
    events.sort(key=lambda e: (e.time is None, e.time if e.time is not None else pd.Timestamp.max))
    return events


def resolve_htf_poi_event(
    events: list[_ParentEvent],
    ltf_time,
    target,
    *,
    window_n: int = 20,
    strict_before: bool = True,
) -> _ParentEvent | None:
    """Resolve the latest *already observable* HTF structure event for a setup.

    Cross-TF causality is decided by real timestamps, never by bar_index.  In
    strict mode (the default) a parent confirmed on the same close as the LTF
    event is NOT eligible; this prevents fabricating a parent/child sequence in
    one candle.  ``window_n`` limits only the number of already-observed
    candidates inspected; it never opens a future window.
    """
    tnum = _direction_to_num(target)
    if tnum == 0:
        return None
    tt = pd.to_datetime(ltf_time, utc=True, errors="coerce")
    if pd.isna(tt):
        return None
    prior = []
    for event in events:
        if event.direction != tnum or event.time is None or pd.isna(event.time):
            continue
        et = pd.to_datetime(event.time, utc=True, errors="coerce")
        if pd.isna(et):
            continue
        if (et < tt) if strict_before else (et <= tt):
            prior.append(event)
    if window_n:
        prior = prior[-int(window_n):]
    return prior[-1] if prior else None


def make_htf_structure_anchor_fn(
    ltf_frame: pd.DataFrame,
    htf_frames: dict[str, pd.DataFrame],
    parents: tuple[str, ...] = _HTF_PARENTS,
    window_n: int = 20,
):
    """Return ``fn(i, target) -> MarketObject | None`` with real HTF provenance.

    This is a STRUCTURE CONTEXT anchor, not an institutional POI zone. It
    returns the latest D1/H4/H1 BOS/CHOCH confirmed on a strictly earlier close,
    preserving the original TF, timestamp and bar index. The sequence may use
    it as an immutable parent of its liquidity/sweep narrative, but it does not
    authorize a trade and does not fabricate an OB/FVG POI.
    """
    from engine.market_object import MarketObject, ObjectState, ObjectType, Role

    events = build_htf_structure_index(htf_frames, parents)
    if "time" in ltf_frame.columns:
        ltf_times = pd.to_datetime(ltf_frame["time"], utc=True, errors="coerce").reset_index(drop=True)
    else:
        ltf_times = pd.to_datetime(ltf_frame.index, utc=True, errors="coerce").reset_index(drop=True)

    def htf_structure_anchor_fn(i: int, target):
        if i < 0 or i >= len(ltf_times):
            return None
        event = resolve_htf_poi_event(
            events, ltf_times.iloc[i], target, window_n=window_n, strict_before=True
        )
        if event is None:
            return None
        side = "BULL" if event.direction > 0 else "BEAR"
        stamp = pd.to_datetime(event.time, utc=True).value
        level = float(event.level) if event.level is not None else 0.0
        typ = ObjectType.BOS if event.kind == "BOS" else ObjectType.CHOCH
        return MarketObject(
            id=f"HTF_CONTEXT_{event.tf}_{event.kind}_{stamp}_{side}",
            symbol="",
            type=typ,
            origin_tf=event.tf,
            role=Role.CONTEXT,
            direction=int(event.direction),
            zone_low=level,
            zone_high=level,
            creation_time=event.time,
            state=ObjectState.ACTIVE,
            bar_index=event.bar_index,
            bar_time=event.time,
            candidate_bar=event.bar_index,
            candidate_time=event.time,
            confirmation_bar=event.bar_index,
            confirmation_time=event.time,
            tradable_bar=event.bar_index,
            tradable_time=event.time,
            meta={
                "producer": "engine.poi_anchor.make_htf_structure_anchor_fn",
                "context_only": True,
                "not_a_poi_zone": True,
                "strictly_before_ltf": True,
                "structure_kind": event.kind,
            },
        )

    return htf_structure_anchor_fn

def make_htf_poi_fn(
    ltf_frame: pd.DataFrame,
    htf_frames: dict[str, pd.DataFrame],
    parents: tuple[str, ...] = _HTF_PARENTS,
    window_n: int = 20,
):
    """Devuelve htf_poi_fn(i, target) -> bool para run_sequence.

    True si en los TF padre hay un BOS/CHOCH en la MISMA direccion que `target`
    ya CERRADO (time <= time de la vela LTF i). BONUS (no veto): si no hay
    eventos padre cargados, devuelve True (no bloquea el historico).
    """
    events = build_htf_structure_index(htf_frames, parents)
    # time del LTF por indice
    if "time" in ltf_frame.columns:
        ltf_times = pd.to_datetime(ltf_frame["time"], utc=True).reset_index(drop=True)
    else:
        ltf_times = pd.to_datetime(ltf_frame.index).reset_index(drop=True)

    # indice por direccion para consulta rapida
    by_dir: dict[int, list[_ParentEvent]] = {1: [], -1: []}
    for e in events:
        if e.direction in by_dir:
            by_dir[e.direction].append(e)

    def htf_poi_fn(i: int, target) -> bool:
        tnum = _direction_to_num(target)
        if tnum == 0:
            return False
        if not by_dir[tnum]:
            return True  # sin eventos padre -> no bloquea (comportamiento historico)
        if i < 0 or i >= len(ltf_times):
            return False
        ltf_t = ltf_times.iloc[i]
        prior = [e for e in by_dir[tnum] if e.time is not None and e.time <= ltf_t]
        prior = prior[-window_n:] if window_n else prior
        return bool(prior)

    return htf_poi_fn


def poi_present(
    ltf_frame: pd.DataFrame,
    htf_frames: dict[str, pd.DataFrame],
    i: int,
    target,
    parents: tuple[str, ...] = _HTF_PARENTS,
) -> bool:
    """True si en los TF padre hay BOS/CHOCH en la MISMA direccion que `target`.

    Wrapper de make_htf_poi_fn para anotar metadata (poi_present) en el
    backtest SIN que el backtest tenga su propia logica de POI. El motor es
    la unica fuente (Ley). Anti look-ahead por timestamp cross-TF.
    """
    return bool(make_htf_poi_fn(ltf_frame, htf_frames, parents=parents)(i, target))