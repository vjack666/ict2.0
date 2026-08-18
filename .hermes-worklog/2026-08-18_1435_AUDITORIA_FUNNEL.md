# Bitácora — Auditoría Funnel EURUSD H1/H4/D1

**Fecha:** 2026-08-18 14:35 UTC-5  
**Autor:** Hermes  
**Pedido:** auditoría funnel + data de internet + reporte a GitHub con guía de recomendaciones

---

## Trabajo realizado

1. Regenerados parquet válidos desde CSV ejtraderLabs (precios ×100000 → reales).
2. Auditoría de integridad: 0 nulls, 0 dups, 0 bad OHLC, orden temporal OK.
3. Funnel de detección ejecutado (swing → BOS → CHOCH → real → class) con IA off.
4. Resultados: H1 10 CHOCH real / 562 unique (~1.8 %); H4 2 real; D1 0 real.
5. Documento completo: `docs/AUDITORIA_FUNNEL_EURUSD_H1_H4_D1.md` con guía R1–R11.

## Artefactos

- `docs/AUDITORIA_FUNNEL_EURUSD_H1_H4_D1.md`
- `data/metadata/EURUSD_H1_H4_D1.json`
- `data/metadata/funnel_audit_H1_H4_D1.json`
- `data/raw/EURUSD/*.parquet` (gitignored)

## Veredicto

PASS CON RESTRICCIONES. Data y funnel OK. Premium escaso (dominio). HTF no inyectado.
