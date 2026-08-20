# GitHub CI — orden y propósito

Los workflows se ordenan por prefijo numérico para que GitHub los presente en
el mismo orden en que debe entenderse el proyecto.

| Orden | Workflow | Propósito |
|---:|---|---|
| 00 | `00-hermes-orchestrator.yml` | Gobierno, auditoría Hermes y gates base |
| 10 | `10-hermes-tests.yml` | Suite general de tests |
| 20 | `20-hermes-audit-stack.yml` | Auditoría A0–A9 y funnel FVG/OB |
| 30 | `30-hermes-fvg-ob-funnel.yml` | Funnel FVG/OB + Sequence + MTF |
| 40 | `40-hermes-data-tests.yml` | Datos M5 temporales y tests |
| 41 | `41-hermes-data-tests-diagnostic.yml` | Diagnóstico de datos HTF |

## Política

- `main` es la rama publicada.
- Los workflows tienen permisos de lectura.
- Los datasets grandes se generan como artifacts temporales y no se commitean.
- El workflow de auditoría no equivale a un backtest ni a una autorización de
  ejecución.
- Cambios en `engine/`, `agents/`, `analysis/`, `orchestration/`, `audits/` o
  `docs/` deben pasar la suite y el gate correspondiente.

Las ramas remotas de trabajo se conservan hasta revisar su contenido; no se
eliminan por limpieza automática.
