# Bitácora — WYCKOFF-7/8 y preflight local CME 6E

**Fecha:** 2026-08-26
**Agente:** Codex, CEO operativo
**Departamento:** Dirección/PMO, CDO/Datos, CTO y CRO
**Tarea:** Avanzar ordenadamente hacia el sistema Wyckoff reproducible al 100 % mediante delegación multiagente, contrato W7/W8 y preflight de disponibilidad.
**Status:** `BLOCKED` para certificación; `COMPLETED` para esta fase de diseño y preflight.

## Delegación y dictamen

Se ejecutaron rondas ordenadas de agentes independientes:

- gobernanza/SDD;
- datos/procedencia;
- motor causal;
- metodología estadística;
- red-team/auditoría;
- redacción W7/W8;
- auditoría independiente del contrato;
- auditoría causal del runtime;
- implementador del preflight.

La auditoría final no autoriza declarar `WYCKOFF-7 PASS`. El runtime actual
carece de las secuencias completas, del evaluador de transiciones/rangos y de
los timestamps `appeared_at`/`confirmed_at`; además permanecen consumidores
legacy con autoridad Wyckoff duplicada. El contrato fue corregido para dejar
claro que AHF es la única FSM jerárquica y que Wyckoff es un evaluador
subordinado.

## Cambios de esta misión

- `docs/tesis/PLAN_LTF_ENTRY_LAYER.md`: añadió W7/W8, unidad inferencial
  primaria `range_id`, alias de volumen, unión PIT `6E ↔ EURUSD` y
  `snapshot_at(FULL,t) == snapshot_at(PREFIX,t)`.
- `docs/tesis/SDD_LTF_ENTRY_LAYER.md`: añadió el mismo contrato normativo,
  clasificación de tokens, procedencia OI y reglas de certificación.
- `scripts/audit/wyckoff_cme6e_availability_preflight.py`: nuevo auditor
  local de solo lectura; su único artefacto permitido es el JSON homónimo.
- `reports/audits/data/wyckoff_cme6e_availability_preflight.json`: resultado
  reproducible del preflight.
- `.hermes-index.md`: estado y bloqueadores actualizados.

## Evidencia

- `git diff --check`: PASS.
- `python -m py_compile scripts/audit/wyckoff_cme6e_availability_preflight.py`: PASS.
- Preflight ejecutado con resultado global `BLOCKED`.
- No se encontraron fuentes locales CME `6E` ni `open_interest`.
- EURUSD Dukascopy tiene OHLC spot, pero sus hashes no coinciden con
  `SHA256SUMS`; no se usa como sustituto de CME.
- No hubo descargas, APIs pagadas, mutación de `data/`/`datasets/`,
  backtest, entrenamiento ni experimento.

## Riesgos y siguiente acción

Riesgos: integrar el motor antes de cerrar el contrato podría crear una segunda
autoridad; adquirir datos sin licencia/roll/sesión/PIT podría invalidar todo el
experimento; el worktree sigue DIRTY por cambios preexistentes y de esta
misión.

Siguiente acción ordenada: revisión independiente del contrato W7/W8 desde un
checkout limpio; después registrar/autorizar una fuente CME `6E` con OHLCV/OI,
licencia, rollover, sesiones y join PIT. Solo cuando el preflight pase se puede
implementar el evaluador canónico y sus tests; `EXP-WYCKOFF-CANONICAL-02`, IA y
promoción permanecen bloqueados.

## Corrección posterior a auditoría

La auditoría final detectó dos faltantes documentales y se corrigieron antes
del cierre: la gramática W7 ahora incluye `SOS`, `SOW`, `LPS` y `LPSY`; y la
regla de independencia define intervalos semiabiertos, ordenamiento por
símbolo/venue/timeframe, rechazo de solapamientos, deduplicación por
`range_id` y fixtures mínimos de aceptación. Se mantiene `BLOCKED` porque el
preflight no encontró CME `6E` ni open interest.
