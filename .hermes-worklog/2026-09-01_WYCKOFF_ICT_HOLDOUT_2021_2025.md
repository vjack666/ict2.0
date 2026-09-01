# Evaluación HOLDOUT 2021–2025 — Wyckoff intradía + ICT

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** Codex / CAIO, con controles CDO y CRO.
- **DEPARTAMENTO:** D3 IA, D4 Datos, D5 Assurance y laboratorio.
- **TAREA:** evaluar una vez el candidato C10 congelado sobre M15 histórico
  2021–2025, sin reentrenamiento, sin seleccionar parámetros y sin usar MT5.
- **MODO:** `LOCAL_ONLY`; investigación únicamente.

## STATUS

`HOLDOUT_EVALUATION_COMPLETED_REVIEW` — gate formal `BLOCKED_PROVENANCE`

La evaluación mecánica terminó. El resultado no demuestra edge y la fuente no
puede certificarse todavía: existen anomalías OHLC reproducibles y la licencia/
permitted-use y el momento de adquisición no están resueltos en un manifiesto
formal. No se concede `TRAINING_ELIGIBLE`, no se habilita MT5 y no hay órdenes.

## Fuente y validación

- Fuente: descarga histórica Dukascopy, M15 bid, `volume-units`, CSV mensual.
- Corpus: `datasets/eurusd_dukascopy_intraday_2021_2025/raw_monthly/`.
- Cobertura: 61 archivos, enero de 2021 a enero de 2026; enero de 2026 solo es
  warmup de las últimas 12 barras de diciembre de 2025.
- Total: 126.070 velas; holdout materializado: 65.131 candidatos.
- Holdout: `[2021-01-01, 2026-01-01)` UTC.
- Duplicados: 0 globales y 0 por archivo; monotonicidad: PASS.
- Huecos mayores de 15 minutos: 284; se conservan como huecos de mercado.
- OHLC inconsistente: 9 filas en octubre de 2024. Una segunda descarga fue
  byte a byte idéntica (`sha256=0cd041e7ea62ddfdcf8b54d530cd6014458757063c845e130802db471c56fd86`);
  no se borraron ni corrigieron.
- Validación mecánica: `REVIEW` por anomalías.
- Provenance formal: `BLOCKED` por licencia/permitted-use y acquisition time no
  resueltos, además de las anomalías.
- MT5: no usado; sus parquets operativos permanecen fuera de este corpus.

## Candidato congelado

- ID: `C10`.
- Perfil: `WYCKOFF_ICT_COMBINED`.
- Configuración: `learning_rate=0.02`, `l2=0.001`, `iterations=500`, seed
  `20260831`.
- Artefacto:
  `reports/audits/experiments/ai/wyckoff_intraday_2006_2010_optimization_postcommit_18bb22e/candidate_10_wyckoff_ict_combined_lr0.02_l20.001.json`.
- Hash interno: `a2789a4f2b8db4dc97af53e6fe4907abe77743a98a887165bc4285b8e0bd58c3`.
- Dataset de entrenamiento del modelo: `7a610960...`; no se sustituyó por el
  holdout.
- Evaluación: `fit_executed=false`, `holdout_used_for_fit=false`,
  `shadow_mode=true`, `can_trade=false`.

## Resultado

| Métrica | HOLDOUT |
|---|---:|
| Filas | 65.131 |
| Accuracy C10 | 0,348605 |
| Accuracy baseline mayoritario | 0,338948 |
| Log-loss C10 | 1,108300 |
| Predicción continuation | 267 |
| Predicción reversal | 3.844 |
| Predicción failure | 61.020 |

Por año, la accuracy fue 0,351539 (2021), 0,347001 (2022), 0,349818 (2023),
0,351291 (2024) y 0,343281 (2025). La mejora frente al baseline es pequeña y
el colapso hacia `failure` indica que el candidato no generaliza de forma
útil. Dictamen científico: `NO_EDGE_DEMONSTRATED`.

## Evidencia

- Runner: `scripts/lab/experiments/wyckoff_intraday_holdout_eval.py`.
- Reporte JSON generado: `reports/audits/experiments/ai/wyckoff_intraday_holdout_2021_2025_20260901_152409/holdout_evaluation.json`.
- Pruebas focales posteriores: `8 passed`.
- Graphify actualizado: 12.086 nodos, 20.000 aristas, 1.033 comunidades; el
  límite de visualización HTML no afecta `graph.json` ni `GRAPH_REPORT.md`.
- Commit local del evaluador y loader congelado: `8c5568d`.

## Decisión y siguiente acción

No se toca el holdout para optimizar. No se ajustan SL/TP, no se cambian
parámetros, no se promociona y no se activa Shadow MT5 con este candidato como
si tuviera edge. Siguiente acción: resolver el gate de provenance/anomalías y,
solo si la autoridad lo aprueba, abrir una nueva iteración de investigación
con preregistro separado; cualquier nuevo modelo debe reservar otro bloque OOS.
