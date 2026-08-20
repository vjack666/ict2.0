"""
ACTUALIZADOR MT5 -> ICT SYSTEM (reusa el terminal MT5 de SMC-SYSTEMS).

Estrategia (verificada contra SMC-SYSTEMS/scripts/update_mt5_append.py):
  - Usa el MISMO terminal MT5 ya logueado en la maquina (FundedNext), sin credenciales.
  - Baja la punta reciente por copy_rates_range (agosto->now) y la APPENDE al
    parquet local de ICT SYSTEM/ data/raw/<SYM>_<TF>.parquet (merge por 'time',
    keep=last) para NO pisar el historico existente.
  - Misma nomenclatura de archivo que ya consume el motor (build_features).

Este script debe correr con el Python del SISTEMA (donde MetaTrader5 esta
instalado: C:/Python314/python.exe), NO con el venv de ICT SYSTEM.

Uso:
  C:/Python314/python.exe scripts/update_mt5_ict.py [--symbols EURUSD GBPUSD XAUUSD USDJPY] [--tfs M1 M5 M15 H1 H4 D1]

Requisito: terminal MT5 (FundedNext) ABIERTA y LOGUEADA.
"""

from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\v_jac\Desktop\ICT SYSTEM")
DATA_DIR = ROOT / "data" / "raw"
MT5_TERMINAL_PATH = r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"

TF_MAP = {
    "M1": 1, "M3": 3, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
}
SYMS_DEFAULT = ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"]


def download_tip(symbol: str, tf: str):
    import MetaTrader5 as mt5
    import pandas as pd

    code = TF_MAP[tf]
    now = datetime.now()
    # Baja desde inicio de mes actual -> now (cubre el agujero reciente).
    rates = mt5.copy_rates_range(symbol, code, datetime(now.year, now.month, 1), now)
    if rates is None or len(rates) == 0:
        rates = mt5.copy_rates_from_pos(symbol, code, 0, 50_000)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"MT5 sin datos para {symbol} {tf}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]
    return df.sort_values("time").reset_index(drop=True)


def merge_tip(local_path: Path, tip):
    import pandas as pd
    cols = ["time", "open", "high", "low", "close", "tick_volume", "spread"]
    tip = tip.copy()
    tip["time"] = pd.to_datetime(tip["time"], utc=True, errors="coerce")
    if local_path.exists() and local_path.stat().st_size > 100:
        prev = pd.read_parquet(local_path)
        prev["time"] = pd.to_datetime(prev["time"], utc=True, errors="coerce")
        for c in cols:
            if c not in prev.columns:
                prev[c] = pd.NA
            if c not in tip.columns:
                tip[c] = pd.NA
        merged = (
            pd.concat([prev[cols], tip[cols]], ignore_index=True)
            .drop_duplicates(subset=["time"], keep="last")
            .sort_values("time")
            .reset_index(drop=True)
        )
        return merged
    return tip[cols].reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Append punta MT5 al data/raw de ICT SYSTEM")
    ap.add_argument("--symbols", default=",".join(SYMS_DEFAULT))
    ap.add_argument("--tfs", default="M1 M5 M15 H1 H4 D1")
    args = ap.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.replace(",", " ").split() if s.strip()]
    tfs = [t.strip().upper() for t in args.tfs.replace(",", " ").split() if t.strip()]

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("[!] MetaTrader5 no instalado en este Python (usa el Python del sistema).")
        return 2
    if not mt5.initialize(path=MT5_TERMINAL_PATH):
        print(f"[!] mt5.initialize fallo: {mt5.last_error()}")
        return 3
    acc = mt5.account_info()
    print(f"[*] MT5 conectado: cuenta {acc.login if acc else '?'} server={acc.server if acc else '?'}")
    if not acc or not acc.login:
        print("[!] Terminal no logueada — abre y loguea MT5 antes de correr.")
        mt5.shutdown()
        return 4

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    for sym in symbols:
        sym_dir = DATA_DIR / sym
        sym_dir.mkdir(parents=True, exist_ok=True)
        for tf in tfs:
            try:
                tip = download_tip(sym, tf)
                path = sym_dir / f"{sym}_{tf}.parquet"
                merged = merge_tip(path, tip)
                merged.to_parquet(path, index=False)
                print(f"[OK] {sym} {tf}: {len(merged)} velas, ultima {merged['time'].iloc[-1]}")
                ok += 1
            except Exception as e:
                print(f"[FAIL] {sym} {tf}: {e}")
                fail += 1
    mt5.shutdown()
    print(f"\n[*] Append MT5 -> ICT SYSTEM completo — OK={ok} FAIL={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
