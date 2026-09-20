#!/usr/bin/env python3
"""Control B: inventario de DETECTORES; NO certifica el harness P1.

El runner histórico confundía consultas del contexto con eventos ICT;
la versión anterior permanece en el historial Git para revisión.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == '__main__':
    print('CONTROL B: DETECTOR_INVENTORY_ONLY_NOT_P1_PASS; P1 requires full multi-TF harness and audit.', flush=True)
    cmd = [sys.executable, str(ROOT/'scripts/audit/ict_event_inventory.py'),
           '--clean-code', str(ROOT), '--manifest',
           str(ROOT/'benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json'),
           '--control', 'B', '--out',
           str(ROOT/'reports/audits/experiments/temporal/detector_inventory_B'),
           *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, cwd=ROOT))
