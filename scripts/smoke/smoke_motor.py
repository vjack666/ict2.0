"""FASE 2b — primer arranque real del motor dentro de ICT SYSTEM.

Objetivo: hacer correr engine.market_features.build_features sobre un DataFrame
OHLC y luego AgentOrchestrator, para revelar DONDE se rompe la integracion.
No arreglamos por adelantado: el runtime dicta la primera dependencia.

Como el repo no tiene velas OHLC crudas (data/ml son features ya procesadas),
generamos OHLC sintetico CONTRATO-VALIDO (open/high/low/close/time) para que el
motor arranque. NO es backtest ni validacion de mercado: es el filtro de
"que falta" para la migracion bajo demanda (.hermes.md s.7).
"""
from __future__ import annotations

import os
import sys
import traceback

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def step(label: str, fn):
    print(f"\n[STEP] {label}")
    try:
        return fn()
    except Exception as e:
        print(f"  FALLO: {type(e).__name__}: {e}")
        traceback.print_exc(limit=3)
        return None


def make_ohlc(n: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # random walk de close con volatilidad variable (para que haya swings)
    ret = rng.normal(0, 0.0008, n).cumsum()
    close = 1.0800 + ret
    # velas: open cerca del close previo, high/low con mecha
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.0004, n)))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.0004, n)))
    t = pd.date_range("2026-01-02 00:00", periods=n, freq="15min")
    return pd.DataFrame({
        "time": t,
        "open": open_,
        "high": hi,
        "low": lo,
        "close": close,
    })


def run():
    raw = make_ohlc()
    print(f"  OHLC sintetico: {len(raw)} filas, cols={list(raw.columns)}")

    from engine.market_features import build_features
    feat = step("engine.market_features.build_features(OHLC)", lambda: build_features(raw))
    if feat is None:
        print("\n[BLOQUEO] El motor no arranca. Resolver dependencia e reintentar.")
        return
    print(f"  motor emitio {len(feat.columns)} columnas:")
    for c in feat.columns:
        print(f"    - {c}")

    # Contrato: que columnas esperan los agentes de analysis/
    from analysis.ict_agent import ICTAgent
    needed = getattr(ICTAgent, "REQUIRED_COLUMNS", [])
    print(f"\n[CONTRATO] analysis/ICTAgent requiere: {needed}")
    if needed:
        missing = [c for c in needed if c not in feat.columns]
        print(f"  FALTAN en salida del motor: {missing}")

    from orchestration.orchestrator import AgentOrchestrator
    out = step("AgentOrchestrator.analyze_context(df_motor)",
               lambda: AgentOrchestrator().analyze_context(feat.copy()))
    if out is not None:
        cols = [c for c in out.columns if c.startswith("agent_")]
        print(f"\n[OK] Orquestador produjo {len(cols)} columnas agent_*.")


if __name__ == "__main__":
    run()
