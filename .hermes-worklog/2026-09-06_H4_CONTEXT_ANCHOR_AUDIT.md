# Auditoría H4 como referencia histórica de la secuencia

Fecha: 2026-09-06. Alcance: EURUSD, Q1 2022, replay canónico M15 con H4.
Estado: PASS técnico, `DIAGNOSTIC_ONLY`.

## Pregunta auditada

¿El motor conserva el contexto H4 que existía al nacer el setup, o reevalúa
la secuencia con información posterior y permite que M15/M5 borren esa
referencia?

## Hallazgos antes de la corrección

- H4 ya se cargaba y se consultaba con barras cerradas.
- La secuencia no guardaba el `asof_time` ni el `asof_bar` H4 al confirmar el
  sweep.
- El artefacto de señales no exportaba esa referencia. Por ello era imposible
  comprobar después qué contexto H4 conocía el motor al iniciar la espera.
- La protección de autoridad de `MarketObject` ya impedía que M15 invalidara
  directamente un objeto H4, pero faltaba evidencia persistida por setup.

## Corrección canónica

- `engine.plan.snapshot_tf` ahora identifica la barra cerrada usada mediante
  `asof_time` y `asof_bar`.
- `SequenceState` congela `context_anchor` al confirmar el sweep. En replay
  estándar contiene H4; en contexto multitemporal puede conservar D1/H4/H1.
- La referencia viaja por snapshot/reanudación, `sequence_audit` y la señal
  exportada. No se usa como caché para datos futuros: el contexto posterior
  sigue leyendo solo velas cerradas y solo puede invalidar con estructura HTF
  realmente opuesta.

## Reproducción y resultado

Comando: replay EURUSD M15, rango 2022-01-01 a 2022-03-31, input M15/M5/M1;
el exportador añadió H4 explícitamente. El artefacto produjo 6.073 velas,
237 sweeps, 27 displacement, 19 BOS y 18 señales diagnósticas.

El auditor mecánico verificó las 18 señales:

- 18/18 tienen `context_anchor.layers.H4` con `asof_time` y `asof_bar`.
- 18/18 cumplen `H4 asof_time <= sweep anchor_time <= decision_time`.
- 0 referencias H4 futuras y 0 anclas faltantes.
- `sequence_audit.context_anchors` contiene 237 fotos, una por sweep.

Ejemplo: el sweep de 06-ene-2022 02:45 UTC conservó H4 cerrada de 00:00 UTC,
barra 18, sesgo BULLISH. El displacement posterior no puede sustituir esa
referencia por una vela futura o por un giro menor M15/M5.

## Límites y autoridad

PASS significa integridad temporal y trazabilidad, no edge ni autorización de
trading. Se conservan `can_trade=false`, `DIAGNOSTIC_ONLY`, sin promoción,
órdenes, certificación DatasetSnapshot ni push.

Evidencia: `reports/audits/experiments/ai/v2_h4_context_anchor_q1_audit.json`
y `v2_h4_context_anchor_q1_backtest.json`.
