"""Orquestador de lectura visual matutina ICT SYSTEM (EURUSD).

Best-effort: intenta refrescar la punta MT5 (vía el Python del sistema donde
MetaTrader5 esta instalado) y regenera los charts TradingView-style en
reports/charts/. Lectura SOLAMENTE: no calcula entry/SL/TP ni ordenes.

Uso:
  .venv/Scripts/python scripts/daily/morning_read.py --symbols EURUSD --tfs "D1 H4 H1 M15"
  .venv/Scripts/python scripts/daily/morning_read.py --symbols EURUSD --tfs "D1 H4 H1 M15" --no-mt5
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # scripts/daily -> raiz repo
SYSTEM_PY = r"C:\Python314\python.exe"
MT5_UPDATER = ROOT / "scripts" / "daily" / "update_mt5_ict.py"
CHART_GEN = ROOT / "scripts" / "presentation" / "plot_tradingview_zones.py"
MT5_TIMEOUT_S = 150


def run_mt5(symbols, tfs):
    """Refresco best-effort de la punta MT5. Devuelve True si OK, False si no."""
    if not os.path.exists(SYSTEM_PY):
        print("[WARN] Python del sistema con MetaTrader5 no encontrado; se omite refresh MT5.")
        return False
    cmd = [SYSTEM_PY, str(MT5_UPDATER), "--symbols", " ".join(symbols), "--tfs", tfs]
    print(f"[*] Refresh MT5 best-effort: {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=MT5_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"[WARN] MT5 refresh excedio {MT5_TIMEOUT_S}s; se usa datos local existentes.")
        return False
    if r.stdout:
        print(r.stdout)
    if r.returncode != 0:
        print(f"[WARN] MT5 refresh fallo (rc={r.returncode}). Usando datos locales existentes.")
        if r.stderr:
            print(r.stderr)
        return False
    return True


def gen_charts(symbols, tfs):
    """Genera los charts para cada simbolo. Devuelve lista de simbolos fallidos."""
    failures = []
    for sym in symbols:
        cmd = [sys.executable, str(CHART_GEN), "--symbol", sym, "--tfs", tfs]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        if r.stdout:
            print(r.stdout)
        if r.returncode != 0:
            failures.append(sym)
            if r.stderr:
                print(r.stderr)
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description="Lectura visual matutina EURUSD (read-only)")
    ap.add_argument("--symbols", nargs="*", default=["EURUSD"])
    ap.add_argument("--tfs", default="D1 H4 H1 M15")
    ap.add_argument("--no-mt5", action="store_true", help="Omitir refresh MT5; usar datos locales.")
    args = ap.parse_args()

    if args.no_mt5:
        print("[*] --no-mt5: se omite refresh MT5, se usan datos locales.")
    else:
        run_mt5(args.symbols, args.tfs)

    failures = gen_charts(args.symbols, args.tfs)
    if failures and not args.no_mt5:
        print(f"[!] Charts fallaron para {failures}; reintentando con --no-mt5 (datos locales).")
        gen_charts(failures, args.tfs)

    print("[OK] Lectura visual completa. Charts en reports/charts/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
