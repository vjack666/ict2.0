# Worklog — Auditoría como primer paso de Hermes

**Fecha:** 2026-08-18
**Estado:** IMPLEMENTACIÓN REORGANIZADA / GATE CI PENDIENTE

## Objetivo

Hacer que el arranque local de Hermes ejecute auditorías antes de cualquier fase del plan y que un estado no aceptable fuerce un loop de corrección, pruebas, documentación y nueva auditoría.

## Cambios

### Código canónico

Toda ejecución de auditorías queda bajo:

`audits/codigo/`

Componentes:

- `gate.py`
- `data_integrity.py`
- `temporal.py`
- `funnel.py`
- `bootstrap.py`

Las implementaciones ejecutables antiguas bajo `audits/contracts/`, `audits/checks/`, `audits/core/` y `audits/funnel/` fueron retiradas. Se evita tener dos fuentes de verdad.

### Arranque

Se añadió:

`start_hermes.py`

Su primera y única función es iniciar `audits.codigo.bootstrap`.

### Loop

`AUDIT → FINDINGS → FIX COMMAND → TEST → UPDATE DOCS → AUDIT`

Variables:

- `HERMES_FIX_COMMAND` — comando local del agente Hermes para corregir findings.
- `HERMES_AUDIT_MAX_ITER` — máximo de iteraciones; 5 por defecto.

### Umbral "medianamente bueno"

- cero CRITICAL;
- cero HIGH;
- cero look-ahead;
- A0 PASS;
- A7 PASS cuando corresponda;
- `audit_score >= 0.80`.

El umbral no equivale a PASS de fase; sólo habilita continuar dentro del Gate correspondiente.

## Documentación actualizada

- `audits/README.md`
- `audits/MANIFEST.md`
- `docs/SDD_FUNNEL_AUDIT.md`
- `.hermes/START_HERMES_AUDIT_FIRST.md`
- `.hermes-index.md`

## Evidencia

La ejecución local de la suite completa no se pudo realizar desde esta sesión por limitación de resolución DNS hacia GitHub; no se declara PASS por ausencia de evidencia. GitHub Actions debe verificar la reorganización antes de cerrar el Gate.

## Próximo paso

Ejecutar `python start_hermes.py` en el PC de Hermes, verificar el loop, corregir cualquier fallo y actualizar este worklog con la evidencia real.
