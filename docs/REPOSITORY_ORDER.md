# Orden de evolución del repositorio

Este documento define el orden de trabajo para mantener `ict2.0` profesional
sin romper las APIs activas de `engine/`, `agents/` u `orchestration/`.

## Fase 1 — Autoridad y nombres

1. Un solo contrato normativo por concepto.
2. Los duplicados se convierten en referencias de compatibilidad o se marcan
   como históricos.
3. Cada documento debe declarar estado: `NORMATIVO`, `ACTIVO`, `EVIDENCIA`,
   `HISTÓRICO` o `SUPERSEDED`.

## Fase 2 — Capas activas

1. `engine/` produce el snapshot canónico.
2. `agents/` ofrece la API pública.
3. `analysis/` implementa los agentes.
4. `orchestration/` coordina evidencia y conflictos.
5. `daily_motor.py` conserva la autoridad de la lectura diaria.

No se debe conectar un agente a un DataFrame alternativo si existe un snapshot
canónico equivalente.

## Fase 3 — Separación laboratorio/diario

La separación inicial es lógica para no romper imports:

```text
diario:       engine + brief + reports/daily + docs/briefs
laboratorio:  learning scripts + replay + models + evaluations
auditoría:    audits + reports/audits + CI
```

Solo después de añadir wrappers y tests se crearán subcarpetas físicas como
`lab/learning/` o `runtime/daily/`.

## Fase 4 — Limpieza histórica

Un archivo solo se mueve a histórico si:

- ya no es importado por código activo;
- existe sustituto documentado;
- se conserva su referencia Git;
- los tests y workflows ya no lo necesitan.

Esto aplica especialmente a módulos de OTE/Fibonacci y a outputs antiguos. No
aplica a `agents/` ni `orchestration/`, que permanecen activos.

## Fase 5 — GitHub

- Workflows ordenados por prefijo numérico.
- Un README de CI explica qué gate ejecuta cada workflow.
- Las ramas remotas no se borran automáticamente: primero se verifica si
  contienen trabajo no fusionado y se decide su archivado explícito.
- `main` recibe solo cambios que pasan imports, tests y gates afectados.
