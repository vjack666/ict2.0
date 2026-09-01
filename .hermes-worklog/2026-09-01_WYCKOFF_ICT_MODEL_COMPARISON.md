# Comparación diagnóstica ICT-only vs Wyckoff-only vs combinado

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** Codex / CAIO con auditoría CRO.
- **DEPARTAMENTO:** D3 IA, D4 Datos y D5 Assurance.
- **TAREA:** comparar los perfiles ICT M15, Wyckoff H1/M15 y Wyckoff+ICT
  usando el mismo corpus causal intradía 2006–2010.
- **MODO:** `LOCAL_ONLY`.

## STATUS

`DIAGNOSTIC_COMPARISON_COMPLETED` — las tres variantes terminaron con el mismo
input hash, split temporal, semilla y algoritmo. Esto no es certificación
científica, no demuestra edge y no autoriza MT5 ni órdenes.

## Diseño congelado

- Corpus: `reports/audits/experiments/ai/wyckoff_intraday_2006_2010.jsonl`.
- Filas: 53.761; hash SHA-256:
  `7a610960d3035282db7a0e620b66c4312c66137c1b5f52ff3badab7237da9922`.
- Target: `label_end_12` (12 velas M15, tres horas).
- Split: temporal 60/20/20; TRAIN 32.256, VALIDATION 10.752, TEST/OOS
  10.753.
- Algoritmo: softmax multinomial determinista; semilla `20260831`.
- El HOLDOUT 2021–2025 no fue usado.

## Resultado

| Perfil | Features | TRAIN accuracy | VALIDATION accuracy | TEST/OOS accuracy | TEST/OOS log-loss | Delta vs mayoría |
|---|---:|---:|---:|---:|---:|---:|
| ICT-only | 12 | 0,428664 | 0,398903 | **0,403050** | 1,090154 | +0,004092 |
| Wyckoff-only | 38 | 0,426277 | 0,397135 | 0,400167 | 1,090933 | +0,001209 |
| Wyckoff + ICT | 48 | **0,428912** | **0,398624** | 0,402678 | **1,090112** | +0,003720 |

El baseline de clase mayoritaria en TEST/OOS es aproximadamente 0,398958. La
mejor accuracy pertenece a ICT-only; el combinado mejora marginalmente el
log-loss, pero no supera a ICT-only en accuracy y ninguna variante muestra una
distancia material frente al baseline.

## Dictamen

- **Técnico:** PASS para ejecutar y comparar perfiles registrados.
- **Científico:** `REVIEW`; no hay evidencia suficiente de edge ni de aporte
  incremental robusto de Wyckoff.
- **Seguridad:** `shadow_mode=true`, `can_trade=false`, sin MT5 y sin órdenes.
- **Provenance:** permanece `REVIEW/BLOCKED` para certificación histórica por
  licencia/adquisición y estado de worktree; no se convierte en PASS por el
  resultado del modelo.

## Evidencia

- Reporte final post-commit: `reports/audits/experiments/ai/wyckoff_intraday_2006_2010_comparison_postcommit_e7692d8/comparison.json`.
- Resumen legible: `reports/audits/experiments/ai/wyckoff_intraday_2006_2010_comparison_postcommit_e7692d8/comparison.md`.
- Hash interno del reporte: `99ada9c56b621c856981db01fe15da8b719e7f6ef04424f85148b124e20a6219`.
- Commit de código usado por la comparación:
  `e7692d841871236bd8dd88201e5341ca449d3fcd`.
- Pruebas focales: `11 passed`; suite completa: `445 passed`.

## RIESGOS Y SIGUIENTE ACCIÓN

El corpus histórico y sus salidas permanecen locales; no se publican datos ni
artefactos de investigación mientras la provenance/licencia no esté resuelta.
El siguiente paso es auditar formalmente esta comparación y ejecutar el
HOLDOUT 2021–2025 sin reajustar los modelos. Después deben revisarse
calibración, abstención, drift y estabilidad por año antes de considerar
`TRAINING_ELIGIBLE`.
