#!/usr/bin/env python3
"""Control B: inventario real de detectores, NO 30 polls contados como BOS.

El reporte antiguo rotulaba 30 observaciones D1/H4/H1 como 90 eventos ICT
incluso cuando bos_dir=0. Esta entrada redirige al inventario de detectores
sobre los CSV seleccionados y nunca declara P1 PASS o episodios canónicos.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == '__main__':
    print('CONTROL B: DETECTOR_INVENTORY_ONLY_NOT_P1_PASS; P1 requires full 6-TF harness and audit.', flush=True)
    cmd = [sys.executable, str(ROOT/'scripts/audit/ict_event_inventory.py'),
           '--clean-code', str(ROOT), '--manifest',
           str(ROOT/'benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json'),
           '--control', 'B', '--out',
           str(ROOT/'reports/audits/experiments/temporal/detector_inventory_B'),
           *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, cwd=ROOT))
