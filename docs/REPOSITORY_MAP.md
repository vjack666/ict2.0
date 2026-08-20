# Mapa profesional del repositorio

**Proyecto:** `vjack666/ict2.0`
**Rama de referencia:** `main`
**Actualizado:** 2026-08-20
**Propósito:** indicar qué contiene cada carpeta, quién tiene autoridad y qué
capas deben evolucionar juntas.

## Regla de lectura

Las carpetas `agents/` y `orchestration/` son capas activas del sistema. No se
clasifican como legacy por ser fachadas o por usar compatibilidad. Los módulos
individuales solo se marcan como históricos cuando existe una implementación
posterior que los sustituye y el cambio está documentado.

## Orden de la raíz

| Orden | Ruta | Rol | Estado | Autoridad |
|---:|---|---|---|---|
| 00 | `.github/` | Automatización CI y gates de GitHub | Activo | Workflows |
| 01 | `.hermes/`, `.hermes-index.md`, `.hermes.md` | Gobierno y estado de trabajo | Activo | Contrato Hermes |
| 02 | `.hermes-worklog/` | Bitácora append-only | Activo | Evidencia de trabajo |
| 03 | `governance/` | Roles y protocolos | Activo | Gobierno operativo |
| 04 | `docs/` | Autoridad documental, contratos y tesis | Activo | [`INDICE_AUTORIDAD.md`](INDICE_AUTORIDAD.md) |
| 05 | `engine/` | Motor canónico de mercado | Activo | Fuente de verdad runtime |
| 06 | `agents/` | API pública de agentes | Activo | Contrato de agentes |
| 07 | `analysis/` | Implementación de agentes | Activo | Contratos de análisis |
| 08 | `orchestration/` | Coordinación de agentes | Activo | Contrato de orquestación |
| 09 | `detectors/` | Features por DataFrame | Activo | Contrato de features |
| 10 | `tools/` | Herramientas aisladas y aprendizaje base | Activo | Contratos de tools |
| 11 | `audits/` | Código ejecutable de auditorías | Activo | Gates A0–A9/Funnel/TNA |
| 12 | `scripts/` | Entrypoints, datos, briefs y experimentos | Activo, pendiente de subclasificar | Cada script declara su función |
| 13 | `tests/` | Tests automatizados | Activo | Pytest/CI |
| 14 | `reports/` | Evidencia generada legible | Activo | Reportes publicados |
| 15 | `datasets/` | Fixtures o datasets pequeños versionados | Activo | Metadata del dataset |
| 16 | `data/` | Datos locales grandes, ignorados por Git | Local | Inventario en [`DATA_INVENTARIO.md`](DATA_INVENTARIO.md) |

## Capas activas de agentes

```text
engine/ CanonicalSnapshot
    ↓
agents/ API pública estable
    ↓
analysis/ agentes ICT, Structure, Wyckoff, Decision
    ↓
orchestration/ coordinación y evidencia agregada
    ↓
daily_motor.py / briefs / laboratorio
```

`agents/` conserva imports estables como `agents.ict_agent` y
`agents.orchestrator`. `analysis/` contiene la implementación y
`orchestration/` coordina el análisis; ninguna de estas capas puede crear una
segunda autoridad de Context State o AHF.

## Documentación

| Ruta | Contenido |
|---|---|
| `docs/ict/` | Tesis ICT y libros fuente |
| `docs/reglas/` | Rulebooks machine-readable |
| `docs/contratos/` | Contratos normativos de runtime |
| `docs/planificacion/` | SDDs y arquitectura |
| `docs/tesis/` | Planes y SDD LTF/Wyckoff |
| `docs/auditoria/` | Auditorías explicativas |
| `docs/experimentos/` | Interpretación de experimentos |
| `docs/wyckoff/` | Biblioteca teórica Wyckoff |
| `docs/briefs/` | Lecturas publicadas |

Los archivos duplicados en la raíz de `docs/` se mantienen solamente como
compatibilidad hasta que se complete la consolidación documental; la autoridad
se declara en `docs/INDICE_AUTORIDAD.md`.

## Laboratorio y uso diario

El repositorio todavía conserva los scripts de laboratorio dentro de
`scripts/` por compatibilidad. La separación lógica vigente es:

```text
Uso diario: engine/ → scripts/brief_lunes.py → docs/briefs/ y reports/
Laboratorio: scripts/b*.py, train_*.py, data/learning/ y reports de experimentos
```

La siguiente migración puede crear `lab/` con wrappers compatibles; no se deben
mover scripts sin actualizar imports, CI y documentación.

## Datos y outputs

- `data/` no forma parte del árbol versionado normal; se reproduce con scripts
  de adquisición y se documenta con hashes.
- `reports/` contiene evidencia publicada y liviana.
- `graphify-out/` y `graphify-tmp/` son outputs locales ignorados.
- `.venv/` y `.pytest_cache/` son estado local y no son parte del producto.

## Regla de promoción

```text
engine → snapshot canónico → agents → orchestration → lectura/experimento
```

Un agente experimental puede producir evidencia, pero no puede sustituir el
motor canónico, modificar AHF/Context State ni autorizar ejecución.
