# AI Outcome V2 — lista única de recuperación y entrenamiento

Estado: WORKING en organización y preflight; entrenamiento y corrida de tres
meses BLOCKED hasta evidencia de entrada. Dueño: Codex / D3 CAIO. Ejecución
LOCAL_ONLY en el checkout operativo. Este plan reconcilia T1–T9; no reemplaza
el diseño científico ni modifica gates para obtener un resultado favorable.

## Objetivo y criterio de cierre

Entrenar el clasificador de outcomes con datos guardados y features causales
del motor canónico; medir generalización de manera reproducible. Entregar
pesos recargables, manifiestos, configuración, métricas calculadas y auditoría.
can_trade=false, entrenamiento diagnóstico sin promoción automática. Mantener
V1 y raw intactos. No convertir V1 plano a V2 inventando campos ausentes.

## Lista priorizada con dependencias

| ID | Trabajo | Dueño | Depende de | Estado actual | Evidencia necesaria para cerrar |
|---|---|---|---|---|---|
| R0 | Reconciliar afirmaciones de cierre V2 | D1 + D5 | — | COMPLETED en este plan | Identificación de tests superficiales, stubs y métricas no reproducidas; addendum visible |
| R1 | Inventariar datos guardados y cobertura conjunta | D4 | — | WORKING | Filas, TF, fechas, fuente, bytes, hashes; separar raw, V1 y V2; OHLC/duplicados/huecos |
| R2 | Congelar contrato de experimento | D3 + D5 | R1 | WAITING | Fuente autorizada, target/horizonte, población, exec_tf, splits, semilla, métricas y coste computacional definidos antes de resultados |
| R3 | Reparar adapter causal | D2 | R2 | READY para diseño detallado | Snapshot canónico real por evento; eliminar fallback que devuelve frame completo; ningún placeholder usado como observación |
| R4 | Actualizar funnel y backtest de verificación | D2 + D5 | R3 | WAITING | Parámetros fechas/TF/warmup/cortes/output; registrar contexto, BOS, zonas, micro, abstenciones y razones; conservar rechazados y denominadores |
| R5 | Reconstruir materialización V2 | D3 | R3,R4 | WAITING | JSONL con features_at_t, tiempos, lineage, label y label_end_time; manifest real; tri-state preservado; rechazos auditados |
| R6 | Sustituir gates superficiales | D5 | R3,R4,R5 | WAITING | FULL y PREFIX ejecutados independientemente, igualdad por evento en ambos sentidos y varios cortes; pruebas que fallen con futuro, hash incorrecto o campo omitido |
| R7 | Ejecutar funnel/backtest por tres meses | D6 + D5 | R1–R6 PASS | BLOCKED | Trimestre congelado con cobertura necesaria; comando/config/log/hash/commit y conteos por mes; comparación antes/después con mismos datos |
| R8 | Congelar corpus amplio y splits | D3 + D4 | R7 | WAITING | TRAIN/VALIDATION/TEST separados temporalmente, sin labels que crucen cortes; soporte por clase, pesos y población auditables |
| R9 | Entrenar baseline V2_A real | D3 | R8 y gates PASS | BLOCKED | Entrenador existente ejecutado, pesos y normalización aprendidos solo en TRAIN, reload reproduce predicciones y métricas |
| R10 | Ablation A–F comparable | D3 | R9 | WAITING | Mismos IDs/target/splits/semillas/presupuesto; cambia solo set de features; escoger con VALIDATION, nunca con TEST |
| R11 | Evaluar fuera de muestra | D5 | R10 congelado | WAITING | Predicciones reales sobre TEST; baseline, log-loss/Brier, matriz confusión, soporte por clase/segmento e intervalos; registrar selección previa del holdout |
| R12 | Auditoría y cierre | D5 + D1 | R11 | WAITING | Reproducción independiente desde archivos/commit; decisión aceptar diagnóstico o rechazar, memoria y commit selectivo; no trading |

La corrida de tres meses valida la integración, causalidad y contabilidad del
funnel. No sustituye un corpus suficientemente amplio ni demuestra edge por
sí sola. No se fija aquí un trimestre sin conocer cobertura simultánea M1/M5
y HTF. No se reconstruirá M1 desde M15 ni se mezclarán fuentes silenciosamente.

## Hallazgos que deben permanecer visibles

- materializer_t4 escribe una sola secuencia de filas y copia su hash en los
  campos FULL y PREFIX. Esto no es una comparación causal independiente.
- ai_outcome_v2_adapter._prefix_frame devuelve el frame sin cortar ante error;
  debe fallar cerrado. El contexto por defecto usa constantes si faltan features.
- eval_t8 devuelve metadata sin evaluar modelo, predicciones o etiquetas.
- train_v2_full y train_v2_full_run no constituyen entrenamiento reproducible.
- El materializado inspeccionado contiene un registro EP-T4-REPEATED con cuatro
  campos auxiliares, no el corpus de features/labels requerido por el trainer.
- Los valores del JSON V2_A_summary son resultados declarados, no verificados
  mediante comando/dataset/predicciones reproducibles en esta revisión.
- Buscar nombres de funciones, contar dimensiones o hashear dos veces el mismo
  archivo no certifica G0–G13. Los 35 PASS anteriores conservan alcance unitario.

## Decisiones a resolver antes de correr

### Inventario preliminar observado (2026-09-05)

| Parquet local EURUSD | Filas | Primer timestamp | Último timestamp |
|---|---:|---|---|
| D1 | 1.735 | 2020-01-02 | 2026-09-04 |
| H4 | 10.393 | 2020-01-02 | 2026-09-04 |
| H1 | 139.321 | 2006-01-01 | 2026-09-04 |
| M15 | 116.204 | 2022-01-02 | 2026-09-04 |
| M5 | 338.904 | 2022-01-02 | 2026-09-04 |
| M1 | 5.792.171 | 2012-01-11 | 2026-09-04 |

Fuente de inventario: agente inventory_training, lectura local sin ejecutar
motor ni entrenamiento. Min/max no demuestra continuidad, calidad ni origen
uniforme; R1 permanece pendiente de auditoría/hash/fuente por archivo. El
solapamiento nominal de seis TF empieza en 2022, no en 2006.

Manifiestos históricos: 180 meses para 2006–2020 y 61 para 2021–2025 más enero
2026. Esto no prueba que incluyan M1/M5. V2 materializado: 121 bytes, una fila.
NPZ V2: 1.224 bytes, claves clf/intercept/n_features/n_samples, declara 48
features y 200 muestras; esas 200 muestras no están reconstruidas por el JSONL
observado. No equiparar tamaño del NPZ con calidad del modelo.

1. El contrato v1 reserva entrenamiento a histórico Dukascopy y separa MT5;
   V2 menciona parquet operativo. Reconciliar el alcance diagnóstico con el
   contrato vigente antes de elegir fuente. Un hash no establece licencia.
2. Alinear exec_tf del diseño V2 (H1) y del snapshot live (M15): no declarar
   equivalencia por usar la misma clase. Parametrizar y documentar el perfil.
3. Congelar target/horizonte: existen referencias H6, H200 y label_end_12.
   No escoger después de ver métricas. Respetar el experimento aplicable.
4. TEST/OOS ya consultado históricamente no vuelve a ser holdout virgen.
   Registrar exposiciones previas y separar confirmación de exploración.
5. El split 60/20/20 del diseño debe excluir ejemplos cuyo label_end_time
   atraviese una frontera; agrupación por episodio evita duplicados cruzados.

## Métricas y productos obligatorios

- Funnel: N entrada, N por etapa/razón/mes, aceptados/rechazados/superseded,
  cobertura de contexto/zonas/BOS/M5/M1 y N abstenciones. Comparación de conjuntos
  e IDs, no solo conteos. Ningún rechazo desaparece para mejorar métricas.
- Datos: hashes esperados vs observados, fuente/licencia/adquisición,
  timestamps de apertura/cierre, auditoría de anomalías sin modificar raw.
- Modelo: baseline de frecuencias calculado en TRAIN; log-loss, Brier,
  precision/recall/F1 por clase y N; AUC solo cuando clases y definición lo
  permitan. PR-AUC no equivale a precision a un umbral.
- Abstención: cobertura y métricas de toda la población y de la población
  retenida; no ocultar los casos abstendidos para inflar rendimiento.
- Reproducción: config.json, source_manifest.json, audit.json, metrics.json,
  predictions, pesos, versiones, logs y commit, en directorio nuevo por run.
  No rellenar estadísticas constantes ni reutilizar informes como ejecución.

## Paralelismo y regla de estados

D4 inventaría datos mientras D5 revisa pruebas y D2 prepara reparaciones en
write sets disjuntos. Materialización, gates, corrida trimestral, entrenamiento
y evaluación respetan dependencias. READY no es PASS; WORKING no es COMPLETED.
Una tarea solo se cierra con su evidencia de aceptación. Si faltan datos o
procedencia, marcar el gate concreto BLOCKED y continuar documentación/tests
sintéticos autorizados; no compensarlo ejecutando entrenamiento.
