# Frecuencia semanal de setups ICT — Resultado del gate FREQ_GATE_2_3_WEEKLY

**Fecha:** 2026-09-17
**Estado:** `FAIL`
**Autoridad:** investigacion local sobre datos existentes; `can_trade=false`; `entry_authorized=false`.

## Metodologia

Se aplicaron los contratos de PO3, Turtle Soup y Silver Bullet (paso 4 del plan) sobre las 292 filas del dataset `setup_grammar_v1` (TRAIN + VALIDATION + TEST_OOS).

Cada fila fue clasificada contra los tres contratos sin modificar `grammar_labels` originales. Se identificaron familias completas (todas las condiciones satisfechas) y se cuantifico la frecuencia semanal.

## Resultados

### Frecuencia por familia (dataset completo 2006-2025)

| Familia | Setup completos | Semanas con setups | Frecuencia promedio |
|---------|-----------------|--------------------|---------------------|
| PO3 | 0 | 0 | 0.000/semana |
| Turtle Soup | 0 | 0 | 0.000/semana |
| Silver Bullet | 0 | 0 | 0.000/semana |
| **Combinado** | **0** | **0** | **0.000/semana** |

### Frecuencia por split

| Split | Candidatos | Eventos completos | Semanas | Frecuencia |
|-------|------------|-------------------|---------|------------|
| TRAIN (2006-2016) | 120 | 0 | 31 | 0.000/semana |
| VALIDATION (2016-2021) | 96 | 0 | 21 | 0.000/semana |
| TEST_OOS (2021-2025) | 76 | 0 | ? | 0.000/semana |

## Analisis de las 6 filas etiquetadas como PASS

El dataset original contiene 6 filas etiquetadas como `PASS`. Al aplicar los contratos estrictos:

- **Ninguna tiene PO3 completo**: faltan fase M (manipulacion en contra del sesgo) y fase D (CHoCH/BOS a favor)
- **Ninguna tiene Turtle Soup completo**: no son contratrend (son setups a favor del HTF)
- **Ninguna tiene Silver Bullet completo**: falta informacion de killzone en el dataset M15

Las 6 filas PASS tienen:
- `pd_array_zone`: USABLE_UNGRADED (zona validada)
- `htf_narrative`: HTF_OK
- `liquidity_sweep`: SWEEP_VALID
- `structure_confirmation`: CONFIRMED

Pero no cumplen ningun contrato de familia completo.

## Veredicto del gate

**FREQ_GATE_2_3_WEEKLY: FAIL**

La frecuencia de familias completas es 0 setups/semana en todo el periodo analizado (2006-2025).

### Razones

1. **Dataset M15 sin informacion de killzone**: Silver Bullet no se puede evaluar completamente
2. **Falta informacion de RR**: ninguna familia puede evaluar el ratio de riesgo/retorno
3. **Las filas PASS no cumplen contratos estrictos**: el dataset etiqueto como PASS casos con evidencia parcial pero incompleta
4. **286 filas ABSTAIN/REJECT**: la mayoria tiene NO_ZONE, lo que impide completar cualquier familia

## Que significa este resultado

Este es un resultado cientifico honesto, no un fallo del plan. Significa que:

1. Con los datos disponibles (M15, 292 filas seleccionadas), no hay poblacion de familias completas que medir
2. La frecuencia natural no se puede estimar como 2-3/semana con este dataset
3. Es necesario ampliar el dataset (agregar M5/M1 con KZ, o usar datos de menor temporalidad) o ajustar los contratos

## Pasos posteriores

Dado que el paso 5 falla (frecuencia insuficiente), los pasos 6-8 del plan no son aplicables con el dataset actual:

- **Paso 6** (fine_execution): no aplica sin familias completas
- **Paso 7** (PASS_EDGE_INTRADIA): no aplica sin poblacion suficiente
- **Paso 8** (dataset de IA): no aplica sin poblacion determinista

## Recomendaciones

1. **Ampliar dataset**: agregar datos M5/M1 con informacion de killzone para evaluar Silver Bullet
2. **Verificar contratos**: revisar si los contratos de familia son demasiado estrictos o si el dataset falta evidencia critica
3. **Continuar con el paso 1 del plan original**: el preflight indica que las fuentes estan verificadas (60/60), pero la frecuencia es insuficiente para el objetivo de 2-3/semana

## Archivos generados

- `scripts/lab/experiments/generate_multimodel_candidates_v1.py` — generador comun implementado
- `scripts/lab/experiments/classify_multimodel_v1.py` — clasificacion paralela implementada
- `reports/ict_temporal_v1/orion/multimodel_candidates_episodes_v1.json` — 292 candidatos con familias
- `reports/ict_temporal_v1/orion/multimodel_classification_ABSTAIN_REJECT_v1.json` — 286 filas clasificadas
- `reports/ict_temporal_v1/orion/ANALISIS_FILAS_PASS_V1.md` — analisis de las 6 filas PASS
- `docs/contratos/FREQ_GATE_2_3_WEEKLY.md` — contrato de gate creado

## Estado del plan

**Paso 1**: COMPLETADO (preflight v2 ejecutado)
**Paso 2**: COMPLETADO (reloj killzone unificado, pero Silver Bullet no certificable sin KZ en dataset)
**Paso 3**: COMPLETADO (clasificacion paralela de 286 filas ABSTAIN/REJECT)
**Paso 4**: COMPLETADO (generador comun implementado)
**Paso 5**: FAIL (FREQ_GATE_2_3_WEEKLY no alcanzado — frecuencia 0/semana)
**Pasos 6-8**: NO APLICABLES (sin poblacion de familias completas)
