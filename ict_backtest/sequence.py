"""ict_backtest/sequence.py — SHIM de compatibilidad (capa desechable).

El motor de secuencias ICT vive en el MOTOR PERMANENTE: ``engine.sequence``.
Este módulo NO contiene lógica: solo re-exporta desde ``engine.sequence`` para
no romper a los llamadores existentes (canonical.py, scripts/, tests/).

Ley arquitectónica (AGENTS.md): ``engine/`` es la única fuente de decisión y
NUNCA importa ``ict_backtest/``. El backtest solo consume el motor. Cero
duplicación de lógica: aquí no hay ninguna implementación propia.
"""

from engine.sequence import (
    SequenceConfig,
    SequenceState,
    run_sequence,
    run_sequence_traced,
    confirmation_window,
    _candle_objects,
    _has_sweep,
    _has_displacement,
    _has_choch,
    _has_bos,
    _htf_has_poi,
    _latest_fvg_zone,
    _latest_ob_zone,
    _touches_zone,
    _direction_from_bias,
)

# _row_at_time: expuesto históricamente por ict_backtest.sequence. Tras migrar
# el motor a engine/, el lookup closed-row vive en engine.plan.
try:
    from engine.plan import _row_at_time as _row_at_time  # type: ignore
except Exception:  # pragma: no cover - fallback de nombre
    try:
        from engine.plan import _closed_row_at_time as _row_at_time  # type: ignore
    except Exception:
        _row_at_time = None  # type: ignore

__all__ = [
    "SequenceConfig",
    "SequenceState",
    "run_sequence",
    "run_sequence_traced",
    "confirmation_window",
    "_candle_objects",
    "_has_sweep",
    "_has_displacement",
    "_has_choch",
    "_has_bos",
    "_htf_has_poi",
    "_latest_fvg_zone",
    "_latest_ob_zone",
    "_touches_zone",
    "_direction_from_bias",
    "_row_at_time",
]
