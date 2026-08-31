# Ejecución 2026-08-31 — prueba mensual de setup IA

## AGENTE / DEPARTAMENTO

- AGENTE: Codex
- DEPARTAMENTO: CAIO / IA, con soporte CTO de replay y CRO de verificación
- TAREA: ejecutar una primera prueba local de setup con un mes de decisiones sin mezclar MT5

## STATUS

`COMPLETED` como prueba técnica; `BLOCKED` para entrenamiento científico/promoción.

## Objetivo y alcance

Se redujo el cálculo para no procesar los 20 años completos en el primer ciclo. El
replay usó las CSV históricas de Dukascopy de 2025 como marco de cálculo para
conservar horizonte futuro, pero solo seleccionó decisiones del 2025-01-01 al
2025-01-31. Los parquets de `data/raw/EURUSD/` de MT5 no fueron usados ni
modificados por esta prueba.

## Evidencia

- Replay: `visual_backtest_2025_01_h200_prefix.json`.
- Candles de cálculo: 6.205 H1; señales seleccionadas: 1; trades: 1.
- Resultado: el único setup fue bearish, terminó en `SL`, etiqueta causal
  `reversal` con horizonte `label_end_200`.
- FULL/PREFIX: `PASS` en cortes 10/25/50/75/90%, `missing=0`.
- Bridge Episodes/Funnel: `PASS`, 1 episodio y 0 rechazos.
- Materialización técnica: 1 fila escrita en
  `visual_backtest_2025_01_outcome_rows.jsonl`, pero `training_eligible=false`.
- Suite completa: `427 passed`.
- Graphify actualizado: 11.299 nodos y 18.751 relaciones.

## Decisión

Un mes sirve para validar la tubería y medir el costo local, pero no alcanza para
entrenar una IA confiable: hay una sola muestra, una sola clase y ninguna
partición DESIGN/VALIDATION/HOLDOUT útil. No se creó snapshot certificado, no se
registró modelo, no se generaron pesos y `can_trade=false` permanece vigente.

El bloqueo adicional de investigación es intencional: la licencia/permitted use
y el log de adquisición de Dukascopy siguen sin estar establecidos. Los hashes
no se trataron como sustituto de licencia.

## Cambios

- `scripts/lab/experiments/ai_outcome_historical_replay.py`: ventana de decisión
  independiente del marco de cálculo; conserva velas posteriores para etiquetar
  outcomes y filtra señales/trades vinculados sin tocar la fuente.
- `tests/test_ai_outcome_historical_replay.py`: 2 pruebas de ventana y vínculo.
- `.hermes-index.md`: estado y siguiente decisión documentados.

## Riesgos / siguiente acción

- Una muestra mensual no permite evaluar generalización ni edge.
- El siguiente ciclo debe usar una ventana más amplia de decisiones o un dataset
  de setups ya materializado, siempre con split temporal y gates científicos.
- MT5 continúa reservado para actualización operativa y futura Shadow Mode; no se
  mezcla con el histórico de investigación.
