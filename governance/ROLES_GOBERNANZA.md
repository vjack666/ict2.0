# ROLES DE GOBERNANZA — Organigrama institucional de SMC-SYSTEMS

Este documento es el **mapa / catálogo ÚNICO** del organigrama institucional. Catálogo
de **ROLES** (responsabilidades). Un rol se instancia en **AGENTES** concretos por tarea.

> Adaptado de `backtest quotex / hermes / ROLES_GOBERNANZA.md`, reestructurado con la
> corrección de arquitectura 2026-08-09: **ROL ≠ AGENTE**, metáfora del EDIFICIO, y
> separación EXPLORACIÓN vs PROMOCIÓN.

## Concepto clave: ROL ≠ AGENTE

- **ROL** = responsabilidad institucional (qué se debe cumplir).
- **AGENTE** = quién ejecuta esa responsabilidad en UNA tarea concreta.

```
ROL: Fiscal de Falsación (Auditor)
        │
        ├── instancia: auditar EXP-071
        ├── instancia: auditar nuevo detector POI
        ├── instancia: auditar backtest
        └── instancia: auditar modificación del motor
```

Los roles son **capacidades institucionales adaptativas**, no bots de una sola tarea.
Pueden aparecer en distintas situaciones (motor, backtest, lab, arquitectura).

## ROL DEL EDIFICIO (metáfora de SMC-SYSTEMS)

```
                    🏛️ EDIFICIO
                       │
                 CONTRATACIÓN
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   INVESTIGA       CONSTRUYE        AUDITA
        │              │              │
     hipótesis        código        evidencia
        │              │              │
        └──────────────┼──────────────┘
                       │
                     PISO
                       │
                 validación
                       │
                 siguiente piso
```

### Pisos del edificio (fases de madurez de una idea)
| Piso | Fase | Qué pasa ahí |
|------|------|--------------|
| 0 | Idea | Nace la pregunta |
| 1 | Hipótesis formalizada | La investiga el Investigador |
| 2 | Experimento | Corre en lab/backtest (libre de fallar) |
| 3 | Evidencia | Resultados medibles |
| 4 | Validación | El Auditor intenta matarla |
| 5 | Candidato | Sobrevive la auditoría |
| 6 | Promoción | Sube a operación (veto del Auditor) |
| 7 | Producción | Vive en `engine/` |

El Auditor dice "no sube de piso"; la Memoria "este piso queda registrado"; Cumplimiento
"no puedes construir aquí, incumple la estructura"; Alertas "hay una grieta en este piso";
Investigador "encontré una posible nueva habitación"; Ingeniero "la construyo".

## ROLES PERMANENTES (institucionales)

| Rol | Reporta a | Responsabilidad (función) | Veto | Archivo |
|-----|-----------|---------------------------|------|---------|
| Director de Investigación (Ruben) | — | Aprobar, declarar edge, decidir roles | Veto último | (humano) |
| Hermes (Orquestador) | Director | Descubrir contexto, enrutar, no decidir solo | — | `ORQUESTADOR.md` |
| Investigador / Analista | Director | Explorar → hipótesis comprobable | — | `investigador.md` |
| Ingeniero | Director | Convertir spec/descubrimiento en implementación verificable | — | `ingeniero.md` |
| Auditor Independiente (Fiscal de Falsación) | Director | Intentar matar hipótesis; veto de **PROMOCIÓN** | Veto promoción | `auditor_independiente.md` |
| Memoria Institucional (Engram Keeper) | Director | Autoridad sobre el registro de conocimiento | Veto de cierre | `memoria_institucional.md` |
| Cumplimiento Operativo | Director | Sandbox, secretos, Ley Fundamental (motor≠backtest) | Veto ejecución | `cumplimiento_operativo.md` |
| Alertas Tempranas | Director | Riesgos/desviaciones con severidad | Forzar `--audit-only` | `alertas_tempranas.md` |
| Motor (SMC/ICT) | Director | Infraestructura neutral (`engine/`) | Sin veto | `engine/` |
| Backtest Canónico (consumidor) | Director | Reloj vela-a-vela, consume `engine/` | Sin veto | `ict_backtest/` |

## Principio rey
> **Quien propone ≠ quien construye ≠ quien audita ≠ quien archiva ≠ quien aprueba.**

## Nota de adaptabilidad
Cada rol es polivalente: cubre motor + backtest + lab EXP-NNN + arquitectura, no una tarea
puntual. Se instancia según la necesidad (ver `ORQUESTADOR.md` → matriz de enrutamiento).

## Nota de unicidad
Los roles viven en `agents/governance/` con responsabilidad única. `auditor_independiente`
es canónico; `fiscal_falsacion` es su alias. Ante duplicación, manda este índice.
