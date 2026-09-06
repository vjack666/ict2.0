# D2/D5 — espera por eventos de la secuencia canónica

Fecha: 2026-09-06. Estado: COMPLETED_DIAGNOSTIC_ONLY.

## Problema corregido

La secuencia vencía por conteo de velas (`displace_gap=6`) antes de que se
confirmara el evento. También podía borrar un escenario sin publicar una causa
de invalidación. La autoridad indicó que el motor debe conservar una lectura
válida y esperar nuevos cierres, sin convertirse en un loop infinito.

## Cambio

- `SequenceConfig.displace_gap` y `bos_gap` usan `None` por defecto: no hay
  timeout arbitrario. Un entero positivo configura un timeout explícito para
  un experimento acotado.
- Cada vela cerrada evalúa primero invalidación estructural congelada, giro
  direccional observable y veto top-down direccional. Contexto neutral o no
  disponible suspende la confirmación, no destruye la secuencia.
- Se añade `sequence_audit`: invalidaciones, pausas comprimidas y estado
  `PENDING_END_OF_DATA`. El fin de datos no genera una señal ni una etiqueta.
- `SequenceRunner` y el recorrido batch comparten la regla estructural; el
  checkpoint ya restaura objetos cuyo nivel ausente fue serializado como JSON
  `null`.
- Backtest y funnel solo transportan el registro. Un funnel sin señales sigue
  `BLOCKED`, con cero episodios y `can_trade=false`.

## Verificación

- `55 passed`: paciencia después de seis velas, BOS tardío, timeout explícito,
  ruptura estructural, contexto neutral, snapshot/reanudación, backtest/funnel
  y regresiones de lifecycle.
- `py_compile` de los módulos modificados: PASS.
- Reproducción única real, EURUSD M15/M5/M1, 2022-Q1:
  `reports/audits/experiments/ai/v2_event_wait_q1_backtest.json`.
  Resultado: 6073 velas, 4898 eventos, 124 sweeps, 0 displacement, 0 BOS,
  0 señales y 0 trades. La política serializada es `EVENT_DRIVEN`; las
  invalidaciones tienen causa (`DIRECTION_FLIP` u `OPPOSITE_SWING_BREAK`), no
  `TIMEOUT`.
- Funnel: `v2_event_wait_q1_funnel.json`, cero episodios, `BLOCKED`; preserva
  el diagnóstico y no crea labels.

## Interpretación

La corrección eliminó la caducidad artificial. No resolvió la ausencia de
displacement en esta configuración V2, ni pretende convertirla en resultado
positivo. Ese hallazgo queda separado: revisar el detector/contexto de
displacement en el motor con un experimento preregistrado.

## Límites

No promoción, no entrenamiento desde el funnel vacío, no orden, `can_trade=false`.
