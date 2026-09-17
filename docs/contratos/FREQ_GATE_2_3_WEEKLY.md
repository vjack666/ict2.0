# FREQ_GATE_2_3_WEEKLY — Frecuencia semanal de setups ICT

## Definicion

Un **setup ICT valido** es un candidato que satisface el contrato completo de al menos una familia (PO3, Turtle Soup, Silver Bullet) con todas sus condiciones satisfechas.

## Meta de investigacion

**2-3 operaciones intradia por semana** en el universo congelado, sin promesa ni obligacion de operar cada semana.

## Metodologia de conteo

1. **Conteo por semana calendario**: para cada semana del periodo analizado, contar cuantos setups completos existen.
2. **Separacion por familia**: cada familia se cuenta independientemente.
3. **Deduplicacion**: un evento economico que satisfaga varias familias cuenta como un solo evento en el conteo combinado.
4. **Split separation**: TRAIN, VALIDATION, TEST_OOS se analizan por separado.
5. **Divulgacion de ausencia**: las semanas sin ningun setup deben ser visibles, no ocultas.

## Criterios de aceptacion del gate

El gate PASS cuando:
- La frecuencia semanal promedio en el periodo VALIDATION alcanza 2-3 semanalmente
- La frecuencia es estable (no depende de pocas semanas con muchos setups)
- No hay países de cobertura que expliquen la frecuencia

El gate FAIL cuando:
- La frecuencia es insuficiente (< 2/semana) en VALIDATION
- La frecuencia es muy variable (depende de outliers)
- No hay cobertura temporal suficiente para estimar frecuencia confiable

## Periodo de analisis

- DESIGN: 2006-01-01 a 2016-01-01 (usado para diseño, no para gate)
- VALIDATION: 2016-01-01 a 2021-01-01 (periodo de gate)
- HOLDOUT/OOS: 2021-01-01 a 2026-01-01 (periodo final, solo una lectura)

## Reglas invariantes

- No ajustar reglas para alcanzar la frecuencia
- Las semanas sin setups cuentan como 0 y deben ser visibles
- Un evento que satisfaga varias familias cuenta una vez en frecuencia combinada
- can_trade=false y entry_authorized=false son campos obligatorios
