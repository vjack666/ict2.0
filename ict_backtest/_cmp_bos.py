"""Compare legacy detectors with the permanent market-structure engine.

This is an explicit research/comparison script. Importing it must not load a
symbol or require a parquet file; run it as a script and pass the symbol.
"""

from __future__ import annotations

import argparse

from detectors.bos import detect_bos as old_bos
from detectors.choch import detect_choch as old_choch
from engine.market_structure import detect_market_structure
from ict_backtest.data_feed import load_frames


def main(symbol: str = "XAUUSD", timeframe: str = "H4") -> int:
    frames = load_frames(symbol, (timeframe,))
    df = frames[timeframe]

    old_bos_table = old_bos(df)
    old_choch_table = old_choch(df)
    old_bos_active = int((old_bos_table["bos_status"] == "active").sum())
    old_choch_any = int((old_choch_table["choch_signal"] != "NONE").sum())
    old_choch_bull = int((old_choch_table["choch_signal"] == "CHOCH_BULLISH").sum())
    old_choch_bear = int((old_choch_table["choch_signal"] == "CHOCH_BEARISH").sum())

    new_table = detect_market_structure(df)
    new_bos_active = int((new_table["bos_status"] == "active").sum())
    new_choch_any = int((new_table["choch_dir"] != 0).sum())
    new_choch_bull = int((new_table["choch_dir"] == 1).sum())
    new_choch_bear = int((new_table["choch_dir"] == -1).sum())

    n = len(df)
    print(f"Velas {timeframe}: {n}")
    print(f"{'':28} VIEJO      NUEVO")
    print(f"{'BOS activos':28} {old_bos_active:6}   {new_bos_active:6}")
    print(f"{'CHOCH total':28} {old_choch_any:6}   {new_choch_any:6}")
    print(f"{'  CHOCH bull':28} {old_choch_bull:6}   {new_choch_bull:6}")
    print(f"{'  CHOCH bear':28} {old_choch_bear:6}   {new_choch_bear:6}")
    rate_old = 1000 * old_choch_any / n if n else 0.0
    rate_new = 1000 * new_choch_any / n if n else 0.0
    print(f"{'CHOCH por 1000 velas':28} {rate_old:6.1f}  {rate_new:6.1f}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--timeframe", "--tf", default="H4")
    args = parser.parse_args()
    raise SystemExit(main(args.symbol, args.timeframe))
