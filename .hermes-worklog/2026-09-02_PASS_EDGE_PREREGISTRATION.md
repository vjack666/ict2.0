# Preregistro PASS_EDGE intradía — 2026-09-02

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** Codex / CRO independiente.
- **DEPARTAMENTO:** D5 Assurance, con límites D3 IA y D4 Datos.
- **TAREA:** crear el preregistro económico intradía
  `EXP-PASS-EDGE-INTRADIA-01` usando el contrato PASS_EDGE y la tesis ICT.
- **MODO:** `LOCAL_ONLY`, documentación únicamente.

## STATUS

`COMPLETED` documentalmente; el preregistro queda
`DRAFT_BLOCKED / NO EJECUTAR`. No se declara `PASS_EDGE`.

## EVIDENCIA

- Write set autorizado: solo el preregistro y este worklog.
- Protocolo congelado: `context_htf (H4) → OB (M15) → FVG (M15) → BOS (M15)
  → displacement (M15) → entry en retorno a zona (M15 EXEC)`.
- Congelados: unidad setup, `net_R`, `R0=0`, particiones DESIGN/VALIDATION/
  HOLDOUT, PIT/FULL-PREFIX, bootstrap por cluster, MDE `+0,10R` y potencia
  `0,80`.
- Dejados `UNKNOWN/BLOCKED`: fill económico, spread/comisión/slippage M15,
  horizonte final, tratamiento de las nueve anomalías OHLC y provenance.
- Se declaró la no-mezcla con `label_end_6`/`label_end_12` de IA.
- No se ejecutaron backtests, entrenamiento, órdenes ni descargas.

## ARCHIVOS

- `docs/experimentos/EXP_PASS_EDGE_INTRADIA_01_PREREGISTRATION.md`
- `.hermes-worklog/2026-09-02_PASS_EDGE_PREREGISTRATION.md`

## RIESGOS

- El checkout ya contenía cambios y artefactos previos; fueron preservados.
- El preregistro no resuelve los bloqueadores económicos ni de provenance.
- El protocolo no concede autoridad operativa ni permite seleccionar horizonte o
  costes después de observar resultados.

## SIGUIENTE ACCIÓN

Completar el contrato económico de fill/costes/horizonte, resolver provenance y
obtener GO independiente en worktree limpio antes de cualquier ejecución.
