# Worklog — EXP-004b Strict Walk-Forward

**Fecha:** 2026-08-18  
**Experimento:** EXP-004b  
**Tipo:** Validación OOS / walk-forward estricto  
**Estado:** `FORMAL_GATE_PASS / OPERATIONAL_EVIDENCE_WEAK`

## Objetivo

Evaluar si el GradientBoostingClassifier mantiene capacidad de ranking fuera de muestra bajo un protocolo temporal estricto, con purging y embargo.

## Protocolo

- Modelo: GradientBoostingClassifier (n=200, depth=3)
- Features: 11 canónicas
- Embargo: 7 días
- Purging: activo
- Folds: expanding window por año
- Label: `label_ep`, horizonte H1 ≈ 1 día
- Universo: CHOCH unique EURUSD H1/H4, 2012–2022

## Resultado

- 9 folds válidos
- PR-AUC medio OOS: 0.317
- Base rate: 0.191
- Lift: 1.66×
- Gate formal: PASS (≥1.5× base y ≥3 folds)
- H1: PR-AUC medio 0.280, std 0.07
- H4: 2 folds, 1–2 positivos por fold → no concluyente

## Hallazgos

1. Existe señal OOS débil en H1, pero no un edge operativo fuerte.
2. El rendimiento cae sustancialmente frente al ROC-AUC in-sample ~0.798.
3. El comportamiento es inestable por régimen/año.
4. El experimento usa `CHOCH unique`, no `choch_real`; no valida el filtro productivo.
5. No se autoriza todavía un peso IA de 15% basado exclusivamente en este resultado.

## Decisión

**PASS FORMAL, NO PASS OPERATIVO.** El experimento habilita continuar la investigación, pero no justificar despliegue ni asignación de peso IA por sí solo.

## Siguiente acción

Ejecutar ablación controlada de `score_n` y comparar contra una especificación equivalente sin esa feature, manteniendo el mismo protocolo temporal.

## Artefacto

`data/learning/pipeline/experiments/EXP-004b_walkforward_strict/walkforward_strict.json`
