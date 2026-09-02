# Contrato PASS_EDGE intradía económico — 2026-09-02

## AGENTE / DEPARTAMENTO / TAREA

- **AGENTE:** Codex / CRO independiente.
- **DEPARTAMENTO:** D5 Assurance, con límites D3 IA y D4 Datos.
- **TAREA:** crear el contrato operativo de `PASS_EDGE` para un baseline
  económico intradía sin IA, sin ejecutar backtest, entrenamiento ni órdenes.
- **MODO:** `LOCAL_ONLY`, documentación únicamente.

## STATUS

`COMPLETED` — contrato creado y verificado como diff local. Esto no declara
`PASS_EDGE` de ningún experimento.

## EVIDENCIA

- Se definieron `PASS_EDGE`, `NO_EDGE`, `REVIEW` y `BLOCKED` con precedencia y
  veto de provenance.
- Se fijaron unidad por setup/episodio, `net_R` después de costes, baseline nulo
  `R0=0`, horizonte económico preregistrado, particiones temporales, MDE
  `+0,10R`, potencia `0,80`, IC, bootstrap por cluster, Holm/Bonferroni y
  estabilidad por periodo/sesión/régimen.
- Se separaron explícitamente `label_end_6` y `label_end_12` como contratos IA,
  fuera del baseline económico.
- Verificación realizada: formato Markdown y `git diff --check` sin hallazgos.

## ARCHIVOS

- `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md`
- `.hermes-worklog/2026-09-02_PASS_EDGE_CONTRACT.md`

## RIESGOS

- El checkout ya contenía cambios y artefactos no relacionados; fueron
  preservados.
- El contrato es normativo para futuras evaluaciones, no sustituye el
  preregistro de un experimento concreto ni resuelve la provenance bloqueada.

## SIGUIENTE ACCIÓN

Crear un preregistro económico concreto que complete los campos obligatorios,
resolver provenance y obtener auditoría independiente antes de cualquier
evaluación que pueda producir un veredicto económico.
