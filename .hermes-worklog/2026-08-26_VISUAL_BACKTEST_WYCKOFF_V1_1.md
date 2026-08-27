# Misión — Replay visual causal ICT + Wyckoff v1.1

**Fecha:** 2026-08-26
**Branch:** `codex/visual-replay-wyckoff-v1-1-20260826`
**Base:** `6a653d0769c13e359f303094b327b3ab3c590dea`
**Departamentos:** D2 Ingeniería, D4 Datos, D5 Assurance, D7 Delivery
**Estado:** COMPLETED — diagnóstico local; sin promoción ni trading

## Objetivo y límites

Convertir la muestra React del ZIP externo en un replay real y causal del
runtime ICT + Wyckoff vigente. `engine/` permanece canónico; `backtest/` solo
normaliza disponibilidad, construye prefijos, orquesta APIs y serializa. No se
modificó `engine/`, no se descargaron datos y no se escribió en los Parquet.

La lista de escritura original se amplió únicamente en dos archivos exigidos
por `AGENTS.md`: `backtest/README.md` para documentar el entrypoint v1.1 y
`.hermes-index.md` para cerrar el índice maestro. La razón y el alcance quedan
registrados aquí; no hubo expansión funcional fuera del replay.

## Contrato implementado

- Schema `visual_backtest.json` v1.1 fail-closed y escritura atómica.
- Semántica MT5 demostrada como `OPEN_TIME`; cada frame usado por el motor
  recibe `time=bar_close_time`, con source/open/close conservados.
- Warmup oculto de 200 filas por TF y proyección a índices visibles contiguos.
- Timeline real por cada M15: `MTFNavigator` +
  `engine.Wyckoff.build_wyckoff_snapshot`, delta observacional y eventos
  deterministas con identidad del engine preservada.
- Autoridad H1; capas Wyckoff D1/H4/H1/M15; M5/M1 solo observacionales.
- Hashes de archivo/slice/config/contenido, `run_id` estable y rutas relativas.
- Timeline normativo con `ict.context`, `ict.visible_event_ids`, `wyckoff` y
  `first_seen_decision_time`; manifest con límites de warmup/as-of y lineage
  operativo completo fuera de la identidad científica.
- React/Vite con gráfico de velas, Swing/BOS/CHOCH, eventos/rango Wyckoff,
  operaciones observacionales, controles, carriles MTF, evidencia y carga JSON.
- Servidor `127.0.0.1` de solo lectura con rechazo de traversal y métodos de
  escritura.
- Flags invariantes: `diagnostic_only=true`, `entry_authorized=false`,
  `can_trade=false`, `can_train=false`, `promotion_authorized=false`.

## Corrida EURUSD real de preflight

- Run de preflight: `754246186ffda66956e0b92d` (schema previo a la
  autoauditoría final; no es el artefacto autoritativo de entrega).
- Ventana visible: `2026-08-17T00:15:00Z` a `2026-08-21T23:45:00Z`.
- M15 visible: 479 velas; D1 4, H4 29, H1 119, M5 1.439, M1 7.199.
- Warmup: 200 filas en D1/H4/H1/M15/M5/M1.
- Eventos: 522 ICT; 293 Wyckoff; 1 operación observacional.
- Volumen: `TICK_VOLUME_PROXY` en los seis TF.
- Los artefactos de `backtest/runs/` se ignoran en Git. El run autoritativo se
  genera después de inmovilizar el commit para que `git_commit` y
  `generator_worktree_clean_before_run=true` sean verificables sin
  autorreferencia del worklog.

## Hallazgos de autoauditoría corregidos

- Se añadieron `git_branch`, limpieza previa, versiones Python/Node, comando y
  lineage del motor a `run_metadata`.
- Se adoptaron los nombres exactos del contrato para ventana, timeline,
  eventos Wyckoff y manifest; las rutas permanecen relativas.
- El resultado de una operación M5/M1 se proyecta a la primera vela principal
  cuyo cierre es posterior o igual a la salida, no a la vela anterior.
- El validador rechaza OHLC incoherente, timestamps duplicados/desordenados,
  asof futuro, autoridad ausente, padres tardíos, outcomes prematuros, volumen
  desconocido y hashes/configuración inconsistentes.

## Evidencia de verificación

- `pytest` focal con `ICT_REAL_DATA_DIR`: **17 passed**, 1 warning preexistente
  de Pandas en `engine/bias/narrative.py`.
- FULL-vs-PREFIX sintético y ventana EURUSD real pequeña: PASS.
- `npm ci --prefix backtest/viewer`: 68 paquetes instalados desde lockfile.
- `npm test --prefix backtest/viewer`: **2 passed**.
- `npm run build --prefix backtest/viewer`: PASS, 4.577 módulos; bundle
  principal 429,66 kB (134,77 kB gzip).
- `python -m py_compile`: PASS.
- `python scripts/architecture_guard.py`: PASS.
- Dos exportaciones CLI idénticas: payload y hash idénticos, PASS.
- Servidor: GET/HEAD 200, path traversal 400, POST 405.
- Navegador: reset/anterior/siguiente/play/pausa/velocidad/slider/fecha/capas/
  teclado PASS; consola 0 errores/warnings; futuro posterior al cursor ausente.
- Responsive: 1363×936, 768×900 y 390×844 sin overflow horizontal.
- Design QA: `backtest/viewer/design-qa.md`, `final result: passed`.
- Graphify: 5.931 nodos, 10.244 relaciones, 496 comunidades.

## Riesgos y limitaciones

- El runtime es básico y no implementa la FSM WYCKOFF-7; `range_id` y
  `episode_id` permanecen nulos.
- `tick_volume` es proxy MT5, no volumen real de exchange.
- El visor aporta observabilidad causal; no demuestra edge, suficiencia
  científica, autorización de entrada, trading, entrenamiento o promoción.
- La corrida completa prioriza prefijos cerrados y tarda varios minutos; no es
  un servicio de baja latencia.

## Siguiente acción

Inmovilizar el commit local selectivo y generar desde el worktree limpio el run
autoritativo para inspección humana. Cualquier expansión a WYCKOFF-7,
experimento científico, datos nuevos, ejecución o publicación requiere una
misión y autoridad separadas. No se hace `git push`.
