"""
ACTUALIZADOR MT5 -> ICT SYSTEM (reusa el terminal MT5 de SMC-SYSTEMS).

Estrategia (verificada contra SMC-SYSTEMS/scripts/update_mt5_append.py):
  - Usa el MISMO terminal MT5 ya logueado en la maquina (FundedNext), sin credenciales.
  - Baja las ultimas 50k velas por copy_rates_from_pos (nunca pide rangos
    puntuales al servidor: copy_rates_range puede colgarse cuando la terminal
    no tiene el rango en cache) y filtra desde la ultima fecha del parquet.
  - APPENDE al parquet local (merge por 'time', keep=last) para NO pisar el
    historico existente.
  - Misma nomenclatura de archivo que ya consume el motor (build_features).

Este script debe correr con el Python del SISTEMA (donde MetaTrader5 esta
instalado: C:/Python314/python.exe), NO con el venv de ICT SYSTEM.

Uso:
  C:/Python314/python.exe scripts/update_mt5_ict.py [--symbols EURUSD GBPUSD XAUUSD USDJPY] [--tfs M1 M5 M15 H1 H4 D1]

Requisito: terminal MT5 (FundedNext) ABIERTA y LOGUEADA.
"""

from __future__ import annotations
import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\v_jac\Desktop\ICT SYSTEM")
DATA_DIR = ROOT / "data" / "raw"
MT5_TERMINAL_PATH = r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"

TF_MAP = {
    "M1": 1, "M3": 3, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
}
# Velas por dia por timeframe, para pedir solo lo necesario a MT5.
BARS_PER_DAY = {"M1": 1440, "M3": 480, "M5": 288, "M15": 96, "M30": 48,
                "H1": 24, "H4": 6, "D1": 1}
SYMS_DEFAULT = ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"]


def last_date_from_parquet(path: Path):
    """Return the last timestamp in an existing parquet, or None."""
    import pandas as pd
    if not path.exists() or path.stat().st_size <= 100:
        return None
    try:
        df = pd.read_parquet(path, columns=["time"])
        if df.empty:
            return None
        last = pd.to_datetime(df["time"], utc=True).max()
        return last.to_pydatetime()
    except Exception:
        return None


def download_tip(symbol: str, tf: str, since: datetime | None = None, count: int = 5_000):
    import MetaTrader5 as mt5
    import pandas as pd

    code = TF_MAP[tf]
    # copy_rates_from_pos baja las ultimas `count` velas sin pedir historia
    # puntual al servidor (copy_rates_range puede colgarse cuando la terminal
    # no tiene el rango en cache). Luego se filtra por `since`.
    rates = mt5.copy_rates_from_pos(symbol, code, 0, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"MT5 sin datos para {symbol} {tf}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]
    df = df.sort_values("time").reset_index(drop=True)
    if since is not None:
        df = df[df["time"] > pd.Timestamp(since)].reset_index(drop=True)
    return df


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


def write_parquet_atomic(local_path: Path, frame) -> None:
    """Write a feed through a sibling temp file and replace it atomically.

    Directly opening a large existing parquet for overwrite can fail on
    Windows with ``Invalid argument`` (and a partial write would be unsafe for
    the daily reader). The temporary file is fully materialized first; the
    destination is replaced only after a non-empty artifact exists.
    """
    tmp_path = local_path.with_name(
        f".{local_path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    try:
        frame.to_parquet(tmp_path, index=False)
        if not tmp_path.is_file() or tmp_path.stat().st_size <= 0:
            raise OSError(f"parquet temporal vacío: {tmp_path}")
        # Git status and antivirus can briefly open a large parquet on
        # Windows. Retry only the final replace; never overwrite a partial
        # destination.
        last_error = None
        for attempt in range(20):
            try:
                os.replace(tmp_path, local_path)
                last_error = None
                break
            except OSError as exc:
                last_error = exc
                if attempt == 19:
                    raise
                time.sleep(0.5)
        if last_error is not None:
            raise last_error
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main() -> int:
    ap = argparse.ArgumentParser(description="Append punta MT5 al data/raw de ICT SYSTEM")
    ap.add_argument("--symbols", default=",".join(SYMS_DEFAULT))
    ap.add_argument("--tfs", default="M1 M5 M15 H1 H4 D1")
    ap.add_argument("--max-gap-days", type=int, default=7,
                    help="Saltar parquet si su ultima fecha tiene mas de N dias de gap (evita colgarse en histories limitadas)")
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
                path = sym_dir / f"{sym}_{tf}.parquet"
                last = last_date_from_parquet(path)
                if last:
                    gap_days = (datetime.now(timezone.utc) - last).days
                    if gap_days > args.max_gap_days:
                        print(f"[SKIP] {sym} {tf}: ultima fecha {last} tiene {gap_days} dias de gap (> {args.max_gap_days}); MT5 no tiene esa historia. Usa --max-gap-days mayor si queres intentar.")
                        continue
                    # Agregar 1 segundo para evitar re-descargar la ultima vela
                    since = last + timedelta(seconds=1)
                    # Pedir solo lo necesario para cubrir el gap (+2 dias de margen)
                    count = max(1_000, BARS_PER_DAY.get(tf, 96) * (gap_days + 2))
                    print(f"  {sym} {tf}: parquet existe, ultima fecha {last} -> bajando {count} velas desde {since}")
                else:
                    since = None
                    count = 5_000
                    print(f"  {sym} {tf}: sin parquet previo, bajando ultimas {count} velas")
                tip = download_tip(sym, tf, since=since, count=count)
                merged = merge_tip(path, tip)
                write_parquet_atomic(path, merged)
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
