# Bitácora — Skill `market-data-provenance`

**Fecha:** 2026-08-26
**Agente:** Codex, CEO operativo
**Departamento:** CDO/datos + CRO/assurance + PMO/conocimiento
**Tarea:** Crear el skill especializado de procedencia y reproducibilidad de datos CME/FX.
**Status:** `COMPLETED`

## Alcance

Se creó un skill de auditoría reutilizable para ingestión, unión, validación y
certificación de datos de mercado. Su modo predeterminado es read-only y no
autoriza descargas, experimentos, backtests, entrenamiento ni promoción.

## Controles incluidos

- proveedor, licencia, símbolo/contrato CME `6E` y política de rollover;
- OHLCV, volumen, open interest, unidades y semántica temporal;
- timestamps, timezone, sesiones, huecos, duplicados e invariantes OHLC;
- unión `6E` ↔ `EURUSD` con regla as-of, tolerancia y control PIT;
- hashes SHA-256, manifest, tamaños, versiones, commit generador y worktree;
- estados `PASS`, `REVIEW`, `BLOCKED` y `NOT_RUN`;
- bloqueo explícito de certificación cuando la procedencia es `DIRTY` o incompleta.

## Evidencia

- `quick_validate.py`: `Skill is valid!`.
- Graphify actualizado al cierre: 9.973 nodos, 15.931 aristas, 877 comunidades.
- `git diff --check`: PASS.
- No se modificaron datasets, código de trading ni resultados experimentales.

## Archivos

- `.codex/skills/market-data-provenance/SKILL.md`
- `.codex/skills/market-data-provenance/agents/openai.yaml`
- `.codex/skills/market-data-provenance/references/provenance-checklist.md`
- `.hermes-index.md`

## Riesgos y siguiente acción

El skill define controles, pero todavía no implementa un descargador ni un
certificador automático específico de Databento. El siguiente componente es
`wyckoff-canonical-auditor`, manteniendo la decisión científica dentro del SDD
y sus gates.
