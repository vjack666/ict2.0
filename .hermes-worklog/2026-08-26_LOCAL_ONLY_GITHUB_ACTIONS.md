# Bitácora — Política local y desactivación de GitHub Actions

**Fecha:** 2026-08-26
**Agente:** Codex, CEO operativo
**Departamento:** Dirección/gobierno + CTO/ingeniería + CRO/assurance
**Tarea:** Desactivar GitHub Actions y consolidar la ejecución 100% local.
**Status:** `COMPLETED`

## Acción ejecutada

Se actualizó la configuración de permisos del repositorio mediante la API de
GitHub:

```text
PUT repos/vjack666/ict2.0/actions/permissions
enabled=false
```

La verificación posterior devolvió exactamente `false`. Antes de la acción, el
repositorio reportaba `enabled=true` y siete workflows remotos activos.

## Política consolidada

- GitHub: almacenamiento, ramas, commits, revisión y PR autorizados.
- PC local: tests, funnels, auditorías, experimentos y scripts de laboratorio.
- GitHub Actions: desactivado; los archivos workflow remotos no se eliminan.
- Worktrees temporales nuevos: `C:\Users\v_jac\Desktop\ICT SYSTEM\.hermes-worktrees\`.
- Worktrees históricos existentes: preservados, sin movimiento ni eliminación.
- URLs de correo: nunca compartir la query string posterior a `?` porque puede
  contener `email_token`.

## Evidencia

- `gh auth status`: cuenta `vjack666` autenticada con permiso `repo`.
- `gh api repos/vjack666/ict2.0/actions/permissions`: `enabled=false`.
- `gh workflow list`: siete workflows remotos identificados antes de la
  desactivación.
- `git diff --check`: PASS.

## Riesgos y siguiente acción

Desactivar Actions impide la validación automática remota, pero no sustituye
los gates locales ni convierte un resultado local en certificación científica.
La siguiente tarea debe usar contratos, logs, hashes y auditoría local; no se
debe borrar ningún worktree histórico sin una misión independiente.
