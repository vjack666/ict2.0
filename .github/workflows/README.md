# Workflows desactivados — política local-only

Desde 2026-08-23, por orden de Ruben, este repositorio no ejecuta experimentos,
tests, auditorías, backtests, descargas de datos ni jobs de laboratorio en
GitHub Actions. Todos esos trabajos se ejecutan únicamente en el PC local.

Los workflows históricos fueron retirados de este directorio para impedir
disparadores `push`, `pull_request` o `workflow_dispatch`. GitHub queda como
repositorio, historial y revisión. Véase `.hermes-state/execution_host_policy.md`.
