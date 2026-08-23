# Política de ejecución local-only — 2026-08-23

## AGENTE

Codex / Hermes

## DEPARTAMENTO

D0 Dirección y gobierno, con D1 PMO/conocimiento y D5 Auditoría.

## TAREA

Persistir la orden del cliente de ejecutar en el PC local todos los
experimentos, tests, auditorías, backtests y demás jobs de laboratorio, dejando
GitHub únicamente como repositorio/revisión.

## STATUS

COMPLETED — política documentada localmente; workflows cloud desactivados; sin
experimentos ni jobs ejecutados durante esta tarea.

## EVIDENCIA

- La estrategia anterior clasificaba los procesos pesados como ejecución en
  Grok/nube; fue reemplazada por `docs/EXECUTION_STRATEGY.md`.
- La política normativa queda en `.hermes-state/execution_host_policy.md`.
- El índice maestro registra la decisión y el host único en `.hermes-index.md`.
- Los seis workflows activos de GitHub fueron retirados del directorio de
  workflows; `.github/workflows/README.md` deja constancia de la desactivación.
- No se ejecutaron experimentos, backtests, descargas ni jobs de laboratorio.

## ARCHIVOS

- `docs/EXECUTION_STRATEGY.md`
- `.hermes-state/execution_host_policy.md`
- `.hermes-index.md`
- `.github/workflows/README.md`
- `.hermes-worklog/2026-08-23_LOCAL_ONLY_EXECUTION_POLICY.md`

## RIESGOS

- Los PASS de CI/cloud anteriores son evidencia histórica y no deben confundirse
  con autorización de nuevas ejecuciones remotas.
- La política se hace efectiva en GitHub solo después de commit/push autorizados;
  mientras tanto estos cambios permanecen en el checkout local.
- Un usuario con permisos externos podría reactivar workflows fuera de este
  checkout; cualquier reactivación debe revisarse contra esta política.

## SIGUIENTE ACCIÓN

Antes del próximo experimento autorizado, verificar `git status`, entorno local,
dataset/hash y comando; ejecutar únicamente en el PC y persistir heartbeat y
artefactos. Si el cliente lo autoriza, revisar y publicar estos cambios sin
activar jobs remotos.
