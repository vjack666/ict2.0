"""
CALIBRACIÓN H4/D1 v3: Corrección completa con numpy
======================================================
- Ventanas calculadas con numpy (no pandas .iloc)
- FVG corregido (high[N-1] < low[N+1] para bullish)
- Todos los criterios comparados
"""
import os, json, warnings
from pathlib import Path
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import numpy as np
import pandas as pd

print('='*70)
print('CALIBRACIÓN H4/D1 v3 — numpy corregido')
print('='*70)

BASE = Path(__file__).resolve().parents[2]  # data no copiado a CLEAN; requiere fuente externa / 'data' / 'raw' / 'EURUSD'  # data no copiado a CLEAN; requiere fuente externa
OUT = Path('reports/audits/experiments/displacement')
OUT.mkdir(parents=True, exist_ok=True)

for name, fn in [('H4','EURUSD_H4.parquet'), ('D1','EURUSD_D1.parquet')]:
    df = pd.read_parquet(BASE / fn)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    print(f'\n{"="*60}')
    print(f'{name}: {len(df):,} filas | {df.time.min():%Y-%m-%d} → {df.time.max():%Y-%m-%d}')
    print(f'{"="*60}')

    # Extraer arrays numpy
    _h = df.high.values.astype(np.float64)
    _l = df.low.values.astype(np.float64)
    _o = df.open.values.astype(np.float64)
    _c = df.close.values.astype(np.float64)
    _body = np.abs(_c - _o)
    _range = _h - _l
    _rng_safe = np.where(_range == 0, 1e-10, _range)
    _body_ratio = _body / _rng_safe
    _wick_ratio = 1.0 - _body_ratio
    _avg_range = pd.Series(_range).rolling(14).mean().values

    # Swing detection (numpy)
    half = 5
    sh = np.full(len(df), np.nan); sl = np.full(len(df), np.nan)
    for i in range(half, len(df) - half):
        if _h[i] == _h[i-half:i+half+1].max() and _h[i] > _h[i-half:i].max():
            sh[i] = _h[i]
        if _l[i] == _l[i-half:i+half+1].min() and _l[i] < _l[i-half:i].min():
            sl[i] = _l[i]
    ph = np.where(np.isnan(sh), np.nan, sh)
    pl = np.where(np.isnan(sl), np.nan, sl)
    # forward fill
    for i in range(1, len(ph)):
        if np.isnan(ph[i]): ph[i] = ph[i-1]
        if np.isnan(pl[i]): pl[i] = pl[i-1]
    _sweep_up = (_l < pl) & (~np.isnan(pl))
    _sweep_down = (_h > ph) & (~np.isnan(ph))
    _bos_up = (_c > ph) & (~np.isnan(ph))
    _bos_down = (_c < pl) & (~np.isnan(pl))

    # FVG corregido: high[N-1] < low[N+1] → bullish gap
    _fvg_bull = np.zeros(len(df), dtype=bool)
    _fvg_bear = np.zeros(len(df), dtype=bool)
    for i in range(1, len(df)-1):
        if _h[i-1] < _l[i+1]:
            _fvg_bull[i] = True
        if _l[i-1] > _h[i+1]:
            _fvg_bear[i] = True
    _has_fvg = _fvg_bull | _fvg_bear

    # Displacement B simple (numpy)
    _disp_B = (_body_ratio > 0.60) & (_wick_ratio < 0.20) & (~np.isnan(_body_ratio))

    # Ventana 3 con numpy CORRECTO
    _disp_B_win = np.zeros(len(df), dtype=bool)
    for i in range(len(df)):
        if np.any(_disp_B[max(0, i-2):i+1]):
            _disp_B_win[i] = True

    print(f'\n  Datos base:')
    print(f'  │ displacement velas (body>0.60, wick<0.20): {_disp_B.sum():>6,} | {100*_disp_B.sum()/len(df):.2f}%')
    print(f'  │ displacement ventana 3 (numpy corregido):   {_disp_B_win.sum():>6,} | {100*_disp_B_win.sum()/len(df):.2f}%')
    print(f'  │ FVG presentes:                             {_has_fvg.sum():>6,} | {100*_has_fvg.sum()/len(df):.2f}%')
    print(f'  │ disp + FVG:                                {(_has_fvg & _disp_B).sum():>6,}')
    print(f'  │ disp + FVG + sweep(10 antes):              {sum(1 for i in range(15,len(df)-15) if _disp_B_win[i] and _has_fvg[i] and np.any(_sweep_up[max(0,i-10):i] | _sweep_down[max(0,i-10):i])):>6,}')

    # ── CRITERIO A (actual) ─────────────────────────────────────────────────
    _disp_A = (((_c > _o) & (_body > _avg_range * 2.0) & (_wick_ratio < 0.30)) |
                ((_c < _o) & (_body > _avg_range * 2.0) & (_wick_ratio < 0.30)))
    seqs_A = []
    for i in range(10, len(df) - 8):
        if not _disp_A[i]: continue
        sf, soff = False, -1
        for off in range(1, 6):
            ci = i - off
            if ci < 0: break
            if _sweep_up[ci] or _sweep_down[ci]:
                sf, soff = True, off; break
        if not sf: continue
        bf, boff = False, -1
        for off in range(1, 8):
            ci = i + off
            if ci >= len(df): break
            if _bos_up[ci] or _bos_down[ci]:
                bf, boff = True, off; break
        if not bf: continue
        sd = 1 if _sweep_up[i-soff] else -1
        dd = 1 if (_c[i] > _o[i]) else -1
        bd = 1 if _bos_up[i+boff] else -1
        if sd == dd == bd:
            seqs_A.append(i)

    # ── CRITERIO B (propuesto H4/D1 con FVG) ───────────────────────────────
    seqs_B = []
    for i in range(15, len(df) - 15):
        if not _disp_B_win[i]: continue
        fvg_ok = False
        for j in range(max(0, i-2), min(len(df), i+3)):
            if _has_fvg[j]:
                fvg_ok = True; break
        if not fvg_ok: continue
        sf, soff = False, -1
        for off in range(1, 11):
            ci = i - off
            if ci < 0: break
            if _sweep_up[ci] or _sweep_down[ci]:
                sf, soff = True, off; break
        if not sf: continue
        bf, boff = False, -1
        for off in range(1, 15):
            ci = i + off
            if ci >= len(df): break
            if _bos_up[ci] or _bos_down[ci]:
                bf, boff = True, off; break
        if not bf: continue
        sd = 1 if _sweep_up[i-soff] else -1
        dd = 1 if (_c[i] > _o[i]) else -1
        bd = 1 if _bos_up[i+boff] else -1
        if sd == dd == bd:
            seqs_B.append(i)

    # ── CRITERIO C (B sin FVG) ──────────────────────────────────────────────
    seqs_C = []
    for i in range(15, len(df) - 15):
        if not _disp_B_win[i]: continue
        sf, soff = False, -1
        for off in range(1, 11):
            ci = i - off
            if ci < 0: break
            if _sweep_up[ci] or _sweep_down[ci]:
                sf, soff = True, off; break
        if not sf: continue
        bf, boff = False, -1
        for off in range(1, 15):
            ci = i + off
            if ci >= len(df): break
            if _bos_up[ci] or _bos_down[ci]:
                bf, boff = True, off; break
        if not bf: continue
        sd = 1 if _sweep_up[i-soff] else -1
        dd = 1 if (_c[i] > _o[i]) else -1
        bd = 1 if _bos_up[i+boff] else -1
        if sd == dd == bd:
            seqs_C.append(i)

    # ── RESUMEN ──────────────────────────────────────────────────────────────
    print(f'\n  ┌─ RESULTADOS DE SECUENCIAS ────────────────────────────────────────')
    print(f'  │ CRITERIO A (actual M5/M15):  body>2×avg_range, wick<30%')
    print(f'  │   displacement velas:        {_disp_A.sum():>6,} | {100*_disp_A.sum()/len(df):.3f}%')
    print(f'  │   SECUENCIAS (sweep+BOS):    {len(seqs_A):>6,}')
    if seqs_A:
        br = _body_ratio[seqs_A]
        wr = _wick_ratio[seqs_A]
        rp = _range[seqs_A] * 10000
        print(f'  │   body_ratio: min={br.min():.3f} med={np.median(br):.3f} max={br.max():.3f}')
        print(f'  │   wick_ratio: min={wr.min():.3f} med={np.median(wr):.3f} max={wr.max():.3f}')
        print(f'  │   rango (pips): min={rp.min():.1f} med={np.median(rp):.1f} max={rp.max():.1f}')

    print(f'\n  ├─ CRITERIO B (propuesto +FVG): body>0.60, FVG, wick<20%, sweep10, BOS14')
    print(f'  │ SECUENCIAS (B con FVG):      {len(seqs_B):>6,}')
    if seqs_B:
        br = _body_ratio[seqs_B]
        wr = _wick_ratio[seqs_B]
        rp = _range[seqs_B] * 10000
        print(f'  │   body_ratio: min={br.min():.3f} med={np.median(br):.3f} max={br.max():.3f}')
        print(f'  │   wick_ratio: min={wr.min():.3f} med={np.median(wr):.3f} max={wr.max():.3f}')
        print(f'  │   rango (pips): min={rp.min():.1f} med={np.median(rp):.1f} max={rp.max():.1f}')

    print(f'\n  ├─ CRITERIO C (propuesto -FVG): body>0.60, wick<20%, sweep10, BOS14')
    print(f'  │ SECUENCIAS (B sin FVG):      {len(seqs_C):>6,}')
    if seqs_C:
        br = _body_ratio[seqs_C]
        wr = _wick_ratio[seqs_C]
        rp = _range[seqs_C] * 10000
        print(f'  │   body_ratio: min={br.min():.3f} med={np.median(br):.3f} max={br.max():.3f}')
        print(f'  │   wick_ratio: min={wr.min():.3f} med={np.median(wr):.3f} max={wr.max():.3f}')
        print(f'  │   rango (pips): min={rp.min():.1f} med={np.median(rp):.1f} max={rp.max():.1f}')

    print(f'\n  └─ COMPARACIÓN FINAL ────────────────────────────────────────────────')
    print(f'     A (actual):    {len(seqs_A):4d} secuencias')
    print(f'     B (+FVG):      {len(seqs_B):4d} secuencias  ({"↑"+str(len(seqs_B)-len(seqs_A)) if len(seqs_B)>len(seqs_A) else "↓"+str(len(seqs_A)-len(seqs_B))} vs A)')
    print(f'     C (-FVG):      {len(seqs_C):4d} secuencias  ({"↑"+str(len(seqs_C)-len(seqs_A)) if len(seqs_C)>len(seqs_A) else "↓"+str(len(seqs_A)-len(seqs_C))} vs A)')
    if len(seqs_A) > 0 and len(seqs_B) > 0:
        shared = len(set(seqs_A) & set(seqs_B))
        only_b = len(set(seqs_B) - set(seqs_A))
        print(f'\n     Intersección A∩B: {shared} secuencias compartidas')
        print(f'     Solo en B (nuevas): {only_b} secuencias ({100*only_b/max(1,len(seqs_B)):.1f}% del total B)')
        print(f'     Solo en A (perdidas): {len(set(seqs_A)-set(seqs_B))} secuencias')

    np.savez(OUT / f'seqs_{name.lower()}_calib3.npz',
             idx_A=np.array(seqs_A, dtype=np.int32),
             idx_B=np.array(seqs_B, dtype=np.int32),
             idx_C=np.array(seqs_C, dtype=np.int32))

# ── Tabla final ────────────────────────────────────────────────────────────
print('\n' + '='*65)
print('TABLA COMPARATIVA FINAL — CALIBRACIÓN H4/D1')
print('='*65)
print(f'  {"Timeframe":<10} {"A (actual)":>12} {"B (+FVG)":>12} {"C (-FVG)":>12} {"Mejora B vs A":>15}')
print(f'  {"-"*10} {"-"*12} {"-"*12} {"-"*12} {"-"*15}')
for f in sorted(OUT.glob('seqs_*_calib3.npz')):
    d = np.load(f)
    name = f.stem.replace('seqs_','').replace('_calib3','').upper()
    a = len(d['idx_A']); b = len(d['idx_B']); c = len(d['idx_C'])
    mejora = f'+{b-a} ({(100*(b-a)/max(1,a)):.0f}%)' if b > a else f'{b-a} ({(100*(b-a)/max(1,a)):.0f}%)'
    print(f'  {name:<10} {a:>12,} {b:>12,} {c:>12,} {mejora:>15}')

if len(OUT.glob('seqs_*_calib3.npz')) > 0:
    hf = np.load(OUT / 'seqs_h4_calib3.npz')
    df_ = np.load(OUT / 'seqs_d1_calib3.npz')
    print(f'\n  TOTALES:')
    print(f'  H4: A={len(hf["idx_A"])} seqs, B={len(hf["idx_B"])} seqs, C={len(hf["idx_C"])} seqs')
    print(f'  D1: A={len(df_["idx_A"])} seqs, B={len(df_["idx_B"])} seqs, C={len(df_["idx_C"])} seqs')

print('\n✓ Calibración completada')