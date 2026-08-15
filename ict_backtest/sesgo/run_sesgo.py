#!/usr/bin/env python3
"""Runner real del backtest del sesgo (T8)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

from ict_backtest.sesgo.config import SesgoConfig
from ict_backtest.sesgo.medicion.demostracion import (
    SesgoRow,
    build_demo_report,
    save_demo_report,
)
from ict_backtest.sesgo.motor_cable.cable_bias import CableBias
from ict_backtest.sesgo.reloj.datos import validate_m15_parquet
from ict_backtest.sesgo.reloj.reloj import RelojSesgo


def _future_delta(df: pd.DataFrame, index: int, k: int) -> float | None:
    future = index + k
    if future >= len(df):
        return None
    return float(df.iloc[future]["close"]) - float(df.iloc[index]["close"])


def run_demo(symbol: str = "EURUSD", k: int = 48, max_bars: int = 2000) -> dict:
    config = SesgoConfig()
    validated = validate_m15_parquet(symbol)

    df = validated.df.copy().sort_index()
    if max_bars and max_bars > 0:
        df = df.iloc[:max_bars]

    reloj = RelojSesgo(df, config)
    cable = CableBias(config)

    rows: list[SesgoRow] = []

    for m15_index, ev in enumerate(reloj.iter_eventos()):
        vigente = cable.procesar_evento(ev)
        if vigente is None or not cable.esta_disponible():
            rows.append(
                SesgoRow(
                    m15_index=m15_index,
                    m15_timestamp=ev.m15_timestamp,
                    vigente=None,
                    future_delta=None,
                )
            )
            continue

        delta = _future_delta(df, m15_index, k)
        rows.append(
            SesgoRow(
                m15_index=m15_index,
                m15_timestamp=ev.m15_timestamp,
                vigente=vigente,
                future_delta=delta,
            )
        )

    report = build_demo_report(rows, k=k, symbol=symbol.upper())
    path = save_demo_report(report)
    report["report_path"] = str(path)
    return report


def main() -> int:
    env_symbol = os.environ.get("SMCS_SESGO_SYMBOL")
    symbol = env_symbol or SesgoConfig().symbol_default
    k = int(os.environ.get("SMCS_SESGO_K", SesgoConfig().m15_k_future))
    max_bars = int(os.environ.get("SMCS_SESGO_MAX_BARS", 2000))

    print(f"[sesgo] symbol={symbol} k={k} max_bars={max_bars}")
    report = run_demo(symbol=symbol, k=k, max_bars=max_bars)
    print(f"[sesgo] report={report['report_path']}")
    for row in report["summary"]:
        print(
            f"[sesgo] {row['category']}: aligned={row['aligned']}/{row['total']} ({row['pct']:.2f}%)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
