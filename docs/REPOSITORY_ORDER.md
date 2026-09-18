# Orden de evolución del repositorio

Este documento define el orden de trabajo para mantener `ict2.0` profesional
sin romper las APIs activas de `engine/`, `agents/` u `orchestration/`.

## Fase 0 — Topología Git

Antes de mover archivos o promover una rama:

1. comprobar si las ramas comparten ancestro;
2. si no lo comparten, prohibir el merge automático de historias;
3. seleccionar una rama de integración desde la línea operativa vigente;
4. importar trabajo por unidades verificables con procedencia documentada;
5. conservar las ramas históricas hasta cerrar la reconciliación;
6. no cambiar la rama por defecto hasta pasar los gates afectados.

La política vigente está en
[`REPOSITORY_CANONICAL_STATE.md`](REPOSITORY_CANONICAL_STATE.md).

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

## Fase 3A — Higiene física de la raíz

La raíz no es una carpeta de trabajo. Solo debe contener configuración,
gobierno, entrypoints mínimos y metadatos de instalación.

### Permitido en raíz

```text
README.md
AGENTS.md
requirements.txt
requirements-ai.txt
.python-version
pytest.ini
.gitattributes
.gitignore
.markdownlint.json
opencode.json
start_hermes.py
governance/
docs/
engine/
detectors/
tools/
agents/
analysis/
orchestration/
runtime/
backtest/
audits/
tests/
scripts/
lab/
reports/
data/
datasets/
references/
skills/
mechanical_bot/
```

Los archivos de trabajo, experimentos, notebooks y evidencias nuevas no deben
crearse en raíz.

### Candidatos existentes para migración física

No se mueven automáticamente: primero hay que buscar consumidores, comandos en
documentación y rutas relativas. El destino objetivo es:

| Elemento actual | Destino objetivo | Clase |
|---|---|---|
| `audit_calib_h4d1_v3.py` | `scripts/audit/` | auditoría |
| `audit_extend_all_tf.py` | `scripts/audit/` | auditoría |
| `audit_train_h4d1.py` | `scripts/audit/` | auditoría |
| `validate_blackbox_demo.py` | `scripts/audit/` | auditoría |
| `blackbox_demo_validation_evidence.json` | `reports/audits/` | evidencia |
| `pipeline_full_cpu.py` | `scripts/lab/experiments/` | entrenamiento |
| `smoke_displacement_cpu.py` | `scripts/lab/displacement/` o `scripts/smoke/` tras inspección | smoke/experimento |
| `smoke_single.py` | `scripts/smoke/` | smoke |
| `kaggle_notebook_displacement.ipynb` | `scripts/lab/displacement/notebooks/` | notebook |
| `run_ict_2006_fast.py` | `scripts/lab/experiments/` | replay experimental |
| `run_ict_2006_pipeline.py` | `scripts/lab/experiments/` | replay experimental |
| `mc20260914_mt5_clock_verification.py` | `scripts/audit/` | verificación MT5 |
| `displacement_results/` | `reports/audits/experiments/displacement/` | output |
| `displacement_results_extend/` | `reports/audits/experiments/displacement/` | output |
| `B1_DATA_MANIFEST_V1.json` | mantener temporalmente hasta auditar consumidores | manifest |
| `schema_validate.json` | mantener temporalmente hasta auditar consumidores | schema |
| `design-qa.md` | `docs/maintenance/` o histórico según contenido | documentación |

### Regla de migración

Para cada elemento:

```text
buscar consumidores
→ clasificar autoridad
→ copiar/mover a destino
→ dejar wrapper si es ejecutable y hay consumidores
→ actualizar referencias
→ tests focales
→ suite afectada
→ borrar ruta vieja solo si ya no tiene consumidores
```

No se admite mover diez archivos y reparar después.

## Estructura física objetivo

```text
ICT SYSTEM/
├── governance/          # gobierno, roles, límites
├── docs/                # autoridad, contratos, SDD, tesis, auditoría explicativa
├── engine/              # motor canónico ICT + Wyckoff + estrategias
├── detectors/           # detectores DataFrame/features
├── tools/               # utilidades y validadores reutilizables
├── agents/              # API pública estable
├── analysis/            # implementaciones de agentes
├── orchestration/       # coordinación y Mission Controller
├── runtime/             # observación diaria e infraestructura IA reusable
│   └── ai_learning/
├── backtest/            # replay/economía como consumidor aislado
├── audits/              # framework/gates de assurance
├── tests/               # tests formales
├── scripts/
│   ├── daily/           # operación y refrescos
│   ├── audit/           # runners diagnósticos/auditorías
│   ├── data/            # adquisición/materialización
│   ├── smoke/           # smoke checks
│   ├── presentation/    # gráficos/exports
│   └── lab/
│       ├── experiments/
│       ├── learning/
│       └── displacement/
├── lab/                 # frontera/política del laboratorio; no motor paralelo
├── reports/             # evidencia y salidas publicables
├── data/                # datasets/modelos/artefactos pesados
├── datasets/            # fixtures pequeños/versionados
├── references/          # referencias externas/versionadas
└── skills/              # habilidades del proyecto
```

Wyckoff permanece dentro del sistema canónico: código en `engine/Wyckoff/`,
adaptación en `analysis/wyckoff_agent.py`, tests en `tests/` y teoría en
`docs/wyckoff/`. No se crea una segunda raíz `wyckoff-project/`.

## Fase 4 — Limpieza histórica

Un archivo solo se mueve a histórico si:

- ya no es importado por código activo;
- existe sustituto documentado;
- se conserva su referencia Git;
- los tests locales ya no lo necesitan.

Esto aplica especialmente a módulos de OTE/Fibonacci y a outputs antiguos. No
aplica a `agents/` ni `orchestration/`, que permanecen activos.

## Fase 5 — Ejecución local

- Los tests y gates se ejecutan desde el checkout operativo local.
- La evidencia se conserva en reportes, bitácoras y Engram.
- Las ramas remotas no se borran automáticamente: primero se verifica si
  contienen trabajo no fusionado y se decide su archivado explícito.
- `main` recibe solo cambios que pasan imports, tests y gates afectados.
