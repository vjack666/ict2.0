# Bitácora — Fix flood BOS + parent SH/SL + is_unique en datasets

**Fecha:** 2026-08-17 14:45 UTC-5  
**Estado:** APLICADO en main

## Problema
`detectors/bos.py` marcaba BOS en cada vela mientras close seguía sobre el nivel (ffill + comparación de estado). Una ruptura real generaba docenas de clones → noise artificial ~96–99%.

## Fixes
1. **detectors/bos.py** — BOS = cruce del nivel (prev ≤ nivel < close).
2. **tools/bos.py** — parent_id: BOS_UP↔swing HIGH, BOS_DOWN↔swing LOW.
3. **tools/choch.py** — un CHOCH por (dir, nivel) + cruce.
4. **gen_bos/choch_dataset** — solo `is_unique=True`.

## Prueba
- Sintético 200 velas: 69 → 4 marcas BOS (−94%).
- EURUSD M15: 1292 → 345 (−73%); tools unique 265 → 29.

## Siguiente
Regenerar datasets locales y retomar B4 nature head.
