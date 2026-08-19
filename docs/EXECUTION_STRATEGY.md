# Estrategia de ejecución — ICT 2.0

**Decisión:** 2026-08-19 (Ruben)
**Estado:** VIGENTE

## Regla

| Tipo de proceso | Dónde se ejecuta | Quién lo dispara |
|---|---|---|
| Liviano (A0-A9 audit <1s, smoke tests, lectura de archivos, commits, `git pull/push`) | **Local** — PC de Ruben (20 vCPU / 16 GB) | Hermes, autonomamente |
| Pesado (Funnel 20Y, TNA 20Y, backtest, walk-forward, experimentos pandas/sklearn grandes) | **Grok** — servidores de la nube del Director | Usuario, tras aviso de Hermes |

## Por qué

Se evaluó AWS EC2 (`t4g.small`, cuenta nueva free-tier post-2025-07-15) y se **descartó**:
la cuenta se creó, pero el benchmark local demostró que el cuello de botella del AHF
(`run_timeline` sobre 139k barras H1) es **serial, no paralelo** — 20 cores locales no
ayudaron (timeout 1800s en 1 y en 20 cores). `t4g.small` (2 vCPU/2 GB) no aceleraría nada.
Grok ya dispone de servidores en la nube y es el canal de procesamiento pesado acordado.

Ver `docs/AWS_EXECUTION_HOST.md` (marcado DESCARTADO) para la traza de la evaluación.

## Criterio liviano vs pesado (operativo)

- **Liviano:** termina en segundos; A0-A9 (`audits.codigo.bootstrap`), tests unitarios,
  import smoke, edición/commit de docs y código.
- **Pesado:** procesa el dataset EURUSD 20Y (D1/H4/H1, ~139k barras H1) o corre modelos/
  backtests. El benchmark midió AHF_TEMPORAL en 1800s sin terminar → pesado.

## Protocolo (cuando toca un proceso pesado)

1. Hermes **detecta** que la tarea requiere un proceso pesado.
2. Hermes **AVISA al usuario** en el chat (no lo corre local, no lanza AWS).
3. El usuario lleva el **driver** (ya versionado en `scripts/`) al chat de **Grok**.
4. Grok corre el driver con el dataset 20Y y devuelve:
   - **Resumen** en el chat de Grok.
   - **Informe detallado + métricas** subido a GitHub (`reports/audits/...`).
5. Hermes hace `git pull` y guarda el informe en la PC de Ruben.

## Estado de trabajos pesados

| Job | Driver | Estado |
|---|---|---|
| TNA 20Y (AHF temporal, 2 gates) | `scripts/tna_audit_runner.py` | **PENDIENTE GROK** |
| Funnel 20Y (FVG/OB + secuencia + MTF) | `audits/codigo/mtf_seq_funnel.py` | PENDIENTE GROK (al tocar) |
| Backtest / Walk-forward | por definir (bloqueado hasta A0-A9+Funnel+TNA) | BLOQUEADO |

## Nota de datos

El dataset 20Y vive versionado en `datasets/eurusd_dukascopy_20y/` (SHA256 en `SHA256SUMS`)
y espejado en `data/raw/EURUSD/*.parquet`. Para Grok debe usarse una copia del parquet
o el CSV versionado; el driver `scripts/tna_audit_runner.py` carga `data/raw/EURUSD/*.parquet`.
