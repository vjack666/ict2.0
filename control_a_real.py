#!/usr/bin/env python3
"""Control A: inventario real de detectores. NO es certificación del harness P1.

El runner anterior tomaba CSV.time (apertura) por cierre, usaba la fuente M5
no seleccionada y confundía snapshots de contexto con eventos. La versión
anterior permanece en el historial Git para investigación, pero no debe
seguir generando un JSON con PASS engañoso.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == '__main__':
    print('CONTROL A: DETECTOR_INVENTORY_ONLY_NOT_P1_PASS; P1 requires full 5-TF harness and audit.', flush=True)
    cmd = [sys.executable, str(ROOT/'scripts/audit/ict_event_inventory.py'),
           '--clean-code', str(ROOT), '--manifest',
           str(ROOT/'benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json'),
           '--control', 'A', '--out',
           str(ROOT/'reports/audits/experiments/temporal/detector_inventory_A'),
           *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, cwd=ROOT))
