# Estrategia de ejecución — ICT 2.0

**Decisión:** 2026-08-19 (Ruben)
**Estado:** VIGENTE
**Responsable de pesados:** Grok (servidores de la nube del Director)

---

## 1. Regla general

| Tipo de proceso | Dónde se ejecuta | Quién lo dispara |
| --- | --- | --- |
| Liviano (A0-A9 audit <1s, smoke tests, lectura de archivos, commits, `git pull/push`, edición de docs/código) | **Local** — PC de Ruben (20 vCPU / 16 GB RAM) | Hermes, autónomamente |
| Pesado (Funnel 20Y, TNA 20Y, backtest, walk-forward, experimentos pandas/sklearn grandes sobre EURUSD 20Y) | **Grok** — servidores de la nube del Director | Usuario, tras aviso de Hermes |

**La nube manda.** Cuando hay que correr un proceso pesado, Hermes AVISA en el chat;
el usuario lo lleva al chat de Grok. Nada pesado se corre local ni en AWS.

---

## 2. Por qué (traza)

- Se evaluó AWS EC2 `t4g.small` (cuenta nueva free-tier post-2025-07-15). Se creó la
  cuenta y el IAM user `hermes-ict2-0`, pero se **descartó EC2**.
- Evidencia del benchmark local (`reports/audits/benchmark_spayk.json`, host `spayk`,
  20 cores / 16.8 GB):
  - A0-A9 audit: **0.12 s** (liviano, local).
  - AHF_TEMPORAL (TNA 20Y): **TIMEOUT 1800 s** tanto en 1 como en 20 cores → el cuello
    es **serial** (`run_timeline` procesa 139k barras H1 una por una), no paralelo.
    `t4g.small` (2 vCPU/2 GB) no habría acelerado nada.
- Grok ya dispone de servidores en la nube → es el canal de procesamiento pesado acordado.
- Ver `docs/AWS_EXECUTION_HOST.md` (marcado **DESCARTADO**) para la traza completa de la
  evaluación AWS.

---

## 3. Criterio liviano vs pesado (operativo)

- **Liviano:** termina en segundos. A0-A9 (`audits/codigo/bootstrap`), tests unitarios,
  import smoke, edición/commit de docs y código, `git pull/push`. → **Local**.
- **Pesado:** procesa el dataset EURUSD 20Y (D1/H4/H1; ~139k barras H1) o corre
  modelos/backtests/walk-forward. Benchmark midió AHF_TEMPORAL en 1800s sin terminar → pesado.
  → **Grok**.

---

## 4. PROCEDIMIENTO COMPLETO PARA GROK (copy-paste ready)

Cuando Hermes avisa "toca correr X pesado", seguí estos pasos:

### Paso A — Preparar el entorno en Grok

Pegá esto en el chat de Grok (contexto inicial, una sola vez por sesión):

```
Trabajando en ICT 2.0 (repo github.com/vjack666/ict2.0). Es un motor de trading ICT/SMC
en Python 3.11+. Necesito correr un proceso pesado sobre EURUSD 20Y. El dataset está en
data/raw/EURUSD/ como parquet (EURUSD_D1/H4/H1.parquet) o en datasets/eurusd_dukascopy_20y/
como CSV versionado (SHA256 en SHA256SUMS). Usá pandas 3.x. NO calcules PnL ni emitas
entradas: estas auditorías miden navegación/estructura, no edge. Devolveme (1) resumen
en este chat y (2) un informe JSON detallado + métricas para subir a GitHub en
reports/audits/<nombre>.json.
```

### Paso B — Clonar / traer el repo en Grok

```
git clone https://github.com/vjack666/ict2.0.git
cd ict2.0
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

### Paso C — Asegurar el dataset 20Y

- Si Grok no tiene el parquet: descargalo del repo o subí `EURUSD_*.parquet` desde tu PC
  a la sesión de Grok. El driver `scripts/tna_audit_runner.py` carga `data/raw/EURUSD/*.parquet`.
- Verificá integridad contra `datasets/eurusd_dukascopy_20y/SHA256SUMS` si usás los CSV.

### Paso D — Correr el driver pesado

Para **TNA 20Y** (AHF temporal, 2 gates):

```
. .venv/bin/activate
python scripts/tna_audit_runner.py
# Salida: reports/audits/ahf_temporal_navigation_20Y.json + .md
```

Para **Funnel 20Y** (FVG/OB + secuencia + MTF, sin PnL):

```
. .venv/bin/activate
python -m audits.codigo.mtf_seq_funnel
# Salida: reports/audits/mtf_seq_funnel.json
```

### Paso E — Grok devuelve

1. **Resumen en el chat** de Grok (estado de gates, números clave).
2. **Informe detallado** (`reports/audits/<nombre>.json` + `.md`) → el usuario lo sube a
   GitHub (`git add reports/audits/... && git commit && git push`) o se lo pasa a Hermes
   para que lo guarde en la PC.

### Paso F — Hermes sincroniza a la PC

```
git pull origin main
```

El informe queda en `C:\Users\v_jac\Desktop\ICT SYSTEM\reports\audits\`.

---

## 5. Estado de trabajos pesados

| Job | Driver | Estado |
| --- | --- | --- |
| TNA 20Y (AHF temporal, gates TNA-TRACE-INTEGRITY + TNA-BEHAVIORAL) | `scripts/tna_audit_runner.py` | **PENDIENTE GROK** |
| Funnel 20Y (FVG/OB + secuencia + MTF nav, no PnL) | `audits/codigo/mtf_seq_funnel.py` | PENDIENTE GROK (al tocar) |
| Backtest / Walk-forward | por definir | **BLOQUEADO** hasta A0-A9 + Funnel + TNA |

---

## 6. Notas de datos y límites

- Dataset 20Y versionado: `datasets/eurusd_dukascopy_20y/` (SHA256 en `SHA256SUMS`,
  metadata.json: H1 n=124390 velas 2006-2025) y espejado en `data/raw/EURUSD/*.parquet`.
- El AHF es **single-threaded por barra** (`engine/ahf.py::run_timeline`). Para acelerar
  en Grok, dividir el 20Y en chunks por hilos y mergear snapshots. No es paralelo hoy.
- **No backtest ni entry** hasta cerrar A0-A9 + Funnel + TNA (ver `.hermes-index.md`).
- AWS queda DESCARTADO; `scripts/aws/*` es referencia histórica, no se usa.

---

## 7. Señal para Hermes

Cuando un proceso supere ~60s locales o toque el dataset 20Y completo, Hermes lo marca
PESADO y avisa: "toca correr X en Grok". El usuario lo dispara allá; Hermes solo
sincroniza el resultado a la PC.
