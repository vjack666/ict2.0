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
                events.append(_ParentEvent(time=t, direction=int(bos[i]),
                                           kind="BOS", tf=tf))
            if choch[i] != 0:
                events.append(_ParentEvent(time=t, direction=int(choch[i]),
                                           kind="CHOCH", tf=tf))
    # orden estable por tiempo (los sin tiempo van al final, no anclan)
    events.sort(key=lambda e: (e.time is not None, e.time if e.time is not None else pd.Timestamp.max))
    return events


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