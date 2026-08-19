# Bitácora — Cableado secuencia→MTF + anti-lookahead + funnel

**Fecha:** 2026-08-18 19:05 UTC-5

## Cambios
1. `MTFNavigator` precomputa `run_sequential` y expone depth point-in-time en HAS_SEQUENCE_DEPTH
2. `docs/ANTI_LOOKAHEAD_MTF_SEQUENCE.md` — lógica normativa
3. `audits/codigo/mtf_seq_funnel.py` — funnel FVG/OB + SEQ + MTF nav

## Funnel 20Y
- FVG_OB H1 relations: 702
- SEQ chains: 1460, COMPLETE: 3
- MTF nav samples: 50, audit PASS
