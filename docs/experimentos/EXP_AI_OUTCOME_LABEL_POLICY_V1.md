# Política de etiqueta AI Outcome v1

**Estado:** FROZEN_FOR_NEXT_DIAGNOSTIC_RUN
**Owner:** D3 CAIO, D4 CDO, D5 CRO
**Modo:** LOCAL_ONLY / diagnóstico / `can_trade=false`

## Decisión

La etiqueta `label_end_6` queda conservada como prueba mecánica causal, pero
no es apta para entrenar: en el bloque 2006--2010 produjo solo la clase
`failure`. No se cambia retroactivamente para mejorar una métrica ni se usa
el resultado H200 existente como sustituto, porque su evidencia de entrada no
aporta un FULL/PREFIX aprobado.

Se abre un experimento nuevo, explícitamente diagnóstico, para evaluar las
definiciones ya registradas `label_end_6`, `label_end_24` y `label_end_48`.
No se evalúan SL, TP, PnL, rentabilidad ni accuracy de modelo para elegir.

## Regla de selección mecánica

Para cada candidato, con el mismo productor causal y la misma población de
episodios, se exige antes de formar un corpus:

1. FULL/PREFIX `PASS` en 10/25/50/75/90%.
2. Bridge Episodes/Funnel sin rechazos y con lineage completo.
3. Etiquetas deterministas, sin información futura en `features_at_t`.
4. Al menos 30/10/10 filas en TRAIN/VALIDATION/TEST cronológicos y al menos
   5 filas de cada clase en TRAIN.

Si más de un candidato satisface los cuatro puntos, se elige el de horizonte
más corto (`6`, luego `24`, luego `48`). Si ninguno los satisface, el estado
es `BLOCKED`; no se inventan clases, no se reponderan filas y no se entrena.

## Límites

- Los resultados previos, incluidos H6 y H200, son evidencia diagnóstica
  histórica; no convierten esta selección en confirmatoria.
- Provenance de Dukascopy continúa `BLOCKED`; aun un candidato mecánico apto
  no queda `TRAINING_ELIGIBLE` ni autoriza promoción, MT5 u órdenes.
- El TEST/OOS solo evalúa un candidato congelado: no participa en la elección
  de horizonte, features, hiperparámetros ni calibración.
