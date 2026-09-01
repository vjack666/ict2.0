"""Smoke test FASE 1 — capa de consenso de ict2.0 SIN motor.

Objetivo: confirmar que AgentOrchestrator.analyze_context() corre sobre un
DataFrame sintetico con las columnas que los agentes de analysis/ LEEN
(segun FASE 0: swing_label, bos_direction, choch_signal, liquidity_sweep_*,
fvg_*, ob_*, premium_discount_zone, displacement_*, macro_direction,
d1_direction, atr, tick_volume, stoch_k, stoch_d, high/low/open/close, etc.).

NO importa nada de SMC-SYSTEMS. Prueba solo la capa de consenso aislada.

Uso:  python scripts/smoke_consensus.py
"""
from __future__ import annotations

import os
import sys

# Asegura que la raiz de ICT SYSTEM (donde viven analysis/ y orchestration/)
# este en sys.path aunque se corra el script desde scripts/.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import pandas as pd

from orchestration.orchestrator import AgentOrchestrator
from analysis.ict_agent import ICTAgent
from analysis.structure_agent import StructureAgent
from analysis.wyckoff_agent import WyckoffAgent
from analysis.decision_agent import DecisionAgent


def make_synthetic_df(n: int = 50) -> pd.DataFrame:
    """DataFrame con las columnas que los agentes consumen.

    Coleccion de columnas deducida de analysis/* _read_* en FASE 0.
    Solo necesitamos que existan y sean coherentes; no es data de mercado real.
    """
    rng = np.random.default_rng(42)
    idx = pd.date_range("2026-01-01", periods=n, freq="15min")
    base = 1.1000 + np.cumsum(rng.normal(0, 0.0003, n))
    df = pd.DataFrame(
        {
            "time": idx,
            "open": base,
            "high": base + rng.uniform(0, 0.0005, n),
            "low": base - rng.uniform(0, 0.0005, n),
            "close": base + rng.normal(0, 0.0002, n),
            "tick_volume": rng.integers(100, 1000, n).astype(float),
            "atr": np.full(n, 0.0008),
            "stoch_k": rng.uniform(10, 90, n),
            "stoch_d": rng.uniform(10, 90, n),
            # ICT agent columns
            "swing_label": rng.choice(["HH", "HL", "LH", "LL", None], n, p=[0.25, 0.25, 0.25, 0.2, 0.05]),
            "bos_direction": rng.choice([1.0, -1.0, 0.0], n),
            "choch_signal": rng.choice(["BULLISH", "BEARISH", None], n, p=[0.3, 0.3, 0.4]),
            "choch_dir": rng.choice([1.0, -1.0, 0.0], n),
            "liquidity_sweep_up": rng.choice([True, False], n),
            "liquidity_sweep_down": rng.choice([True, False], n),
            "recent_sweep_up": rng.choice([True, False], n),
            "recent_sweep_down": rng.choice([True, False], n),
            "fvg_bullish": rng.choice([True, False], n),
            "fvg_bearish": rng.choice([True, False], n),
            "fvg_size": rng.uniform(0, 0.001, n),
            "fvg_fill_status": "none",
            "ob_bullish": rng.choice([True, False], n),
            "ob_bearish": rng.choice([True, False], n),
            "ob_distance": rng.uniform(0, 0.002, n),
            "premium_discount_zone": rng.choice(["DISCOUNT", "PREMIUM", "OTE", "NONE"], n),
            "displacement_bullish": rng.choice([True, False], n),
            "displacement_bearish": rng.choice([True, False], n),
            "macro_direction": rng.choice(["BULLISH", "BEARISH", "RANGING"], n, p=[0.4, 0.4, 0.2]),
            "d1_direction": rng.choice(["BULLISH", "BEARISH", "RANGING"], n, p=[0.4, 0.4, 0.2]),
            "trend": rng.choice(["BULLISH", "BEARISH", "RANGING"], n, p=[0.4, 0.4, 0.2]),
            # Structure agent columns
            "market_regime": rng.choice(["TREND", "RANGING"], n),
            "volatility_regime": rng.choice(["HIGH", "LOW"], n),
            "trend_confidence": rng.uniform(0, 1, n),
            "h4_trend": rng.choice(["BULLISH", "BEARISH", "RANGING"], n, p=[0.4, 0.4, 0.2]),
            "range_compression": rng.uniform(0.4, 1.2, n),
            "directional_efficiency": rng.uniform(0.3, 0.9, n),
        }
    )
    return df


def main() -> None:
    df = make_synthetic_df(50)
    orch = AgentOrchestrator(
        ict_agent=ICTAgent(),
        wyckoff_agent=WyckoffAgent(),
        structure_agent=StructureAgent(),
        decision_agent=DecisionAgent(),
    )
    out = orch.analyze_context(df)

    new_cols = [c for c in out.columns if str(c).startswith("agent_")]
    print(f"[OK] analyze_context corrio sobre {len(out)} filas")
    print(f"[OK] columnas agent_* producidas: {len(new_cols)} (esperadas 25)")
    # Muestra de la ultima fila
    last = out.iloc[-1]
    print("[SAMPLE] ultima fila decision:")
    print(f"  agent_decision_bias      = {last.get('agent_decision_bias')}")
    print(f"  agent_decision_confidence= {last.get('agent_decision_confidence')}")
    print(f"  agent_ict_bias           = {last.get('agent_ict_bias')}")
    print(f"  agent_structure_bias     = {last.get('agent_structure_bias')}")
    print(f"  agent_wyckoff_phase      = {last.get('agent_wyckoff_phase')}")
    # Conteo de sesgos no-neutrales para verificar que el combinador reacciona
    non_neutral = (out["agent_decision_bias"] != "NEUTRAL").sum()
    print(f"[STAT] filas con decision != NEUTRAL: {non_neutral}/{len(out)}")
    assert len(new_cols) == 25, f"se esperaban 25 columnas agent_*, salieron {len(new_cols)}"
    print("[OK] FASE 1 smoke test EXITOSO — capa de consenso ict2.0 valida de forma aislada.")


if __name__ == "__main__":
    main()
