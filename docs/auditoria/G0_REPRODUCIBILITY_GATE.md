# G0 — Reproducibilidad y SEQUENCE_PIT_INTEGRITY

**Estado:** PASS acotado — sin promoción de señales ni habilitación de backtest  
**Rama:** `g0-pit-evidence`  
**Runner:** `scripts/audit/sequence_pit_integrity_gate.py`  
**Commit del runner:** `4804ec5540618aae12eb7a0253cbefca2b829922`

## Resultado

El motor secuencial reproduce, en los checkpoints auditados, la misma firma de cadenas observables cuando se ejecuta sobre el prefijo disponible que cuando se ejecuta sobre el dataset completo. La comparación excluye el estado final y cualquier nodo posterior al checkpoint; compara `created_bar`, dirección y nodos `(bar, stage, direction)` hasta el checkpoint.

| Corrida | Cobertura candidata | Checkpoints comprobados | Violaciones | Estado |
|---|---:|---:|---:|---|
| Densa acotada, hasta barra 5.000 | 450 | 40 | 0 | PASS |
| Sparse full-span, checkpoints creados por eventos | 12.100 | 4 | 0 | PASS |

## Reproducibilidad

- Dataset canónico: `datasets/eurusd_dukascopy_20y/EURUSD_H1.csv`.
- Filas: `124.377`.
- SHA256: `2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022`.
- Configuración: `structure_mode=canonical_bos`, `max_active_chains=128`.
- Margen del prefijo: 300 barras cuando el checkpoint lo permite.
- Los JSON reportan `worktree_clean_before_run=true`; la carpeta de salida generada está explícitamente excluida de esa comprobación.

## Artefactos

- `reports/audits/pit/SEQUENCE_PIT_INTEGRITY_BOUNDED.json`
- `reports/audits/pit/SEQUENCE_PIT_INTEGRITY_BOUNDED.md`
- `reports/audits/pit/SEQUENCE_PIT_INTEGRITY_FULL_SPARSE.json`
- `reports/audits/pit/SEQUENCE_PIT_INTEGRITY_FULL_SPARSE.md`

## Límite del gate

Este resultado no es una comprobación exhaustiva de los 12.100 prefijos. Es un gate reproducible con una muestra densa acotada y cuatro checkpoints sparse que cubren inicio, dos puntos intermedios y final del span. Por tanto, habilita preparar los runners B y sus artefactos, pero no cambia hipótesis, no convierte EXP-B en evidencia y no autoriza backtest, promoción ni operación.

Las pruebas de regresión ejecutadas antes del cierre del gate fueron: `17 passed` en los módulos de secuencia, navegación MTF, lineage D y feed LTF canónico.
