# Bitacora — Higiene Git de ramas locales

**Fecha:** 2026-09-21  
**Responsable:** Codex como CEO operativo  
**Estado:** `PARTIAL_CLEANUP_DONE / REVIEW_REQUIRED_FOR_DESTRUCTIVE_NEXT_STEP`

## Objetivo

Reducir deuda operativa de ramas sin poner en riesgo evidencia, worktrees activos
o commits no integrados. Esta limpieza no cambia codigo de motor ni contratos.

## Inventario inicial

- Ramas locales antes de la poda segura: 50.
- Ramas remotas despues de `git remote prune origin`: 39.
- Worktrees registrados: multiples, incluyendo ramas activas y detached
  worktrees bajo `.codex/worktrees`, temporales de causal replay y ramas de
  certificacion/entrenamiento.

## Accion ejecutada

Se eliminaron solo ramas locales ya contenidas en `HEAD`, sin worktree asociado
y no necesarias como rama operativa base:

```text
backup-before-filter-20260915          3ded9afe
codex/audit-hermes-cert-20260826       b277f7c9
preservation/before-causal-replay-install-20260921       340dbe17
preservation/before-causal-replay-install-20260921115840 c29ecbbd
tmp_remote_check                       b277f7c9
```

Comando usado:

```text
git branch -d backup-before-filter-20260915 codex/audit-hermes-cert-20260826 preservation/before-causal-replay-install-20260921 preservation/before-causal-replay-install-20260921115840 tmp_remote_check
```

Tambien se ejecuto:

```text
git remote prune origin
git worktree prune --dry-run
```

`git worktree prune --dry-run` no reporto metadatos obsoletos.

## Estado despues de la poda

- Ramas locales restantes: 45.
- Ramas locales merged en `HEAD`: 5.
- Ramas locales no merged en `HEAD`: 40.
- No se borraron ramas remotas.
- No se removieron worktrees.
- No se hizo `reset`, `clean`, force push ni borrado de archivos.

## Ramas protegidas por criterio

No se tocaron:

- Rama actual: `preservation/before-lineage-hierarchical-integration-20260921`.
- Base operativa reciente: `hermes/evidencia-ict-estado-real-20260920`.
- Ramas con worktree asociado, marcadas por Git con `+`.
- `main`.
- Ramas no mergeadas en `HEAD`.
- Ramas de certificacion, entrenamiento, replay o evidencia que requieren
  revision semantica antes de borrar.

## Diagnostico CEO

El problema principal no son las cinco ramas merged eliminadas; el problema real
es que el repo conserva muchas ramas historicas no integradas o con worktrees
asociados. Eso aumenta el riesgo de:

- empujar desde rama equivocada;
- revisar evidencia vieja como si fuera vigente;
- mantener worktrees temporales despues de cerrar misiones;
- duplicar ramas de preservacion/integracion.

## Politica recomendada

1. Mantener maximo una rama operativa de trabajo por mision activa.
2. Convertir ramas de preservacion cerradas en tags anotados antes de borrar
   ramas locales/remotas.
3. No borrar una rama con worktree asociado sin revisar ese worktree.
4. No borrar ramas no mergeadas sin registrar SHA, proposito y decision.
5. Despues de cada mision cerrada:
   - commit local selectivo;
   - push o PR si se autoriza;
   - cerrar worktree temporal;
   - registrar si la rama queda viva, archivada o borrada.

## Siguiente accion propuesta

Crear una mision separada de archivo seguro:

1. clasificar las 40 ramas no mergeadas;
2. revisar worktrees asociados;
3. crear tags `archive/...` para evidencia que deba conservarse;
4. borrar ramas locales obsoletas;
5. solo despues, borrar remotas obsoletas con autorizacion explicita.
