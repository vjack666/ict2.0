# Auditoría — etiqueta H6 causal y preparación IA

## AGENTE / DEPARTAMENTO

- AGENTE: Codex
- DEPARTAMENTO: D3 CAIO, D4 CDO, D5 CRO y D1 PMO
- TAREA: verificar la etiqueta histórica H6 antes de cualquier entrenamiento.

## Resultado

`label_end_6` es **causalmente reproducible**, pero el bloque 2006--2010 no
es apto para ajuste de IA: tiene 18 filas y las 18 son `failure`.

## Evidencia

- Replay nuevo e inmutable:
  `reports/audits/experiments/ai/replay_2006_2010_h6_prefix_20260902.json`.
- FULL/PREFIX: PASS en 10/25/50/75/90%; conteos 3/3, 5/5, 9/9, 14/14 y 17/17.
- Bridge:
  `reports/audits/experiments/ai/replay_2006_2010_h6_prefix_20260902_funnel.json`;
  18 episodios, 0 rechazos, E0/E1/causal_full_vs_prefix PASS.
- Materialización:
  `reports/audits/experiments/ai/batch_2006_2010_h6_prefix_20260902/`;
  18 filas, distribución `failure=18`.
- Las guardas existentes de `runtime/ai_learning/diagnostic_training.py`
  rechazan corpus sin 30/10/10 filas temporales y sin cinco ejemplos de cada
  clase en TRAIN.

## Dictamen

No hay fallo que corregir en la causalidad de H6. El fallo anterior era la
ausencia de ejecución del gate FULL/PREFIX; se cerró mediante una repetición
inmutable. La insuficiencia de clases no se corrige cambiando la etiqueta tras
ver los resultados. Se congeló una selección mecánica separada en
`docs/experimentos/EXP_AI_OUTCOME_LABEL_POLICY_V1.md`.

## Riesgos

- Provenance de Dukascopy: `BLOCKED` por licencia/uso permitido y adquisición
  no establecidos; no hay certificación ni entrenamiento productivo.
- El antiguo diagnóstico H200 conserva valor histórico, pero no es fuente
  canónica para esta decisión porque su artefacto base no acredita FULL/PREFIX
  aprobado.

## Siguiente acción

Ejecutar los tres candidatos congelados en una población cronológica mayor,
auditar sus gates y, solo si alguno cumple soporte mecánico, usarlo para un
diagnóstico Shadow-only.

## Addendum — ejecución de política 2006--2015

Se ejecutaron `label_end_6`, `label_end_24` y `label_end_48` con la misma
población de 53 episodios y FULL/PREFIX PASS en todos los cortes. El bug de
comparar timestamps como texto fue corregido en `b5fd076`; la comparación ahora
normaliza instantes UTC antes de compararlos.

El resultado fue bloqueo concluyente de soporte: H6=0, H24=2 y H48=3
continuaciones. El materializador canónico mapea TP/SL/OPEN a
continuation/reversal/failure, respectivamente; por tanto ninguna variante
cumple las cinco continuaciones mínimas en TRAIN. No hubo fit de IA, cambio de
SL/TP, trading ni promoción. El resumen con hashes está en
`reports/audits/experiments/ai/label_policy_v1_20260902.json`.
