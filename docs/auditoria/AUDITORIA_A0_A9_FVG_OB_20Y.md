# Auditoría A0–A9 + Funnel FVG/OB — EURUSD 20 años

**Fecha:** 2026-08-18  
**Autor:** Hermes  
**Dataset:** Dukascopy bid vía `dukascopy-node`  
**Rango:** 2006-01-01 → 2025-12-31 (**20.0 años**)  
**IA:** desactivada · **PnL/backtest:** no ejecutado

---

## 1. Objetivo

Ejecutar la pila pre-backtest A0→A9 y el funnel real de detectores FVG/OB sobre historia larga (20Y), no solo el CSV público de ~10 años (ejtraderLabs).

---

## 2. Data

| TF | Barras (limpias) | Rango | Años | Bad OHLC eliminados |
| ---- | ----------------: | ------- | -----: | --------------------: |
| H1 | 124.377 | 2006-01-01 21:00 → 2025-12-31 21:00 | 20.0 | 13 |
| H4 | 32.133 | 2006-01-01 20:00 → 2025-12-31 20:00 | 20.0 | 4 |
| D1 | 6.258 | 2006-01-01 → 2025-12-31 | 20.0 | 0 |

- Orden temporal: OK en los tres TF  
- Duplicados de `time`: 0  
- Escala: precios EURUSD reales (sin ×100000)  
- Fuente distinta a ejtraderLabs (2012–2022)

**A0 real (OHLC completo):** PASS tras limpieza mínima.

---

## 3. Stack A0 → A9 (contratos + smoke + gobernanza)

| Gate | Resultado |
| ------ | ----------- |
| A0 Data Integrity | PASS |
| A1 Schema | PASS |
| A2 Point-in-Time | PASS |
| A3 Semantics | PASS |
| A4 Detector / Metamorphic | PASS |
| A5 Cross-Timeframe | PASS |
| A6 Lineage | PASS |
| A7 Funnel | PASS |
| A8 Coverage / Regime | PASS |
| A9 Governance | PASS |
| **GLOBAL** | **PASS** |

Fingerprint: `ab1bb627d668f52d74f44b6a587c8799394b9c6f8581dc3b439bda21cc5cb538`  
Artefacto: `reports/audits/data/A0_A9_audit_stack.json`

> Nota: A1–A9 del runner contractual usan filas/eventos de smoke + existencia de contratos.  
> A0 real sobre las 124k barras se reporta aparte (`reports/audits/data/A0_real_20Y.json`).

---

## 4. Funnel FVG / OB (detectores canónicos, 20Y)

| TF | Barras | FVG | bull / bear | OB | bull / bear | FVG/bar | OB/bar |
| ---- | -------: | ----: | ------------: | ---: | ------------: | --------: | -------: |
| H1 | 124.377 | 22.478 | 11.253 / 11.225 | 2.799 | 1.346 / 1.453 | 18.1 % | 2.25 % |
| H4 | 32.133 | 6.497 | 3.218 / 3.279 | 862 | 436 / 426 | 20.2 % | 2.68 % |
| D1 | 6.258 | 1.543 | 757 / 786 | 214 | 85 / 129 | 24.7 % | 3.42 % |

- Balance direccional FVG ≈ 50/50 (sano).  
- **Confluencia FVG↔OB:** 0 aceptada — intencional (`NO_FVG/OB_RELATION_AUDITED`).  
  La relación causal formal es trabajo de Fase D/E; este funnel solo mide poblaciones de detector.  
- Artefacto: `reports/audits/experiments/fvg_ob/fvg_ob_funnel.json`

---

## 5. Qué no se afirma

- No se afirma edge ni expectativa de PnL.  
- No se habilita backtest (sigue bloqueado por política del índice hasta evidencia CI + snapshot).  
- No se valida M5.  
- No se autoriza el 15 % de peso IA (EXP-004b sigue siendo evidencia operativa débil).  
- Re-ejecutar el mismo funnel sin cambiar el motor **no aporta información nueva**; solo reproduce densidades.

---

## 6. Comparación breve 10Y (ejtrader) vs 20Y (Dukascopy)

| Aspecto | 10Y (2012–2022) | 20Y (2006–2025) |
| --------- | ----------------- | ----------------- |
| Fuente | ejtraderLabs CSV | Dukascopy bid |
| H1 barras | ~57.6k | ~124.4k |
| Funnel FVG/OB | no medido en aquella corrida CHOCH | medido aquí |
| Integridad A0 | PASS | PASS (tras quitar 17 barras malas) |

Las densidades FVG/OB en 20Y son estables y utilizables como baseline de población de zonas.

---

## 7. Recomendaciones

| ID | Acción | Prioridad |
| ---- | -------- | ----------- |
| R1 | Formalizar regla de confluencia FVG↔OB y re-medir funnel | ALTA |
| R2 | Publicar evidencia en CI (`AUDIT-CI-01`, `AUDIT-FUNNEL-01`) | ALTA |
| R3 | No re-correr funnel idéntico sin cambio de motor | — |
| R4 | Ablación `score_n` / WF solo después de cerrar auditorías CI | MEDIA |
| R5 | Versionar hash SHA256 de los parquet 20Y en metadata | MEDIA |

---

## 8. Artefactos

```
AUDITORIA_A0_A9_FVG_OB_20Y.md          ← este documento
reports/audits/data/A0_A9_audit_stack.json
reports/audits/data/A0_real_20Y.json
reports/audits/experiments/fvg_ob/fvg_ob_funnel.json
data/metadata/EURUSD_20Y.json
data/raw/EURUSD/EURUSD_{H1,H4,D1}.parquet   (gitignored)
```

---

## 9. Gate de esta auditoría

| Criterio | Resultado |
| ---------- | ----------- |
| Data 20Y íntegra | PASS |
| A0–A9 contractual | PASS |
| Funnel FVG/OB ejecutable 20Y | PASS |
| Confluencia auditada | NO (fuera de alcance) |
| Backtest habilitado | NO |

**Veredicto:** `PASS CON RESTRICCIONES` — evidencia local sólida; falta cierre en CI del Director y regla de confluencia antes de backtest.
