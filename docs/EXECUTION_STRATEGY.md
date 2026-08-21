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

**La nube manda.** Cuando hay que correr un proceso pesado, Hermes AVISA en el chat; el usuario lo lleva al chat de Grok. Nada pesado se corre local ni en AWS.

---

## 2. Por qué (traza)

- Se evaluó AWS EC2 `t4g.small` y se **descartó EC2**.
- Evidencia del benchmark local (`reports/audits/infrastructure/benchmark_spayk.json`, host `spayk`, 20 cores / 16.8 GB): A0-A9 audit ~0.12 s; AHF_TEMPORAL serial llegó a timeout de 1800 s antes del parche de navegación.
- El motor `engine/mtf_navigation.py` recibió posteriormente una optimización O(n) de precompute; la regresión publicada reporta equivalencia bit-exact frente al motor anterior en 600 layer-checks.
- Grok ya dispone de servidores en la nube → es el canal de procesamiento pesado acordado.
- Ver `docs/AWS_EXECUTION_HOST.md` (marcado **DESCARTADO**) para la traza completa de la evaluación AWS.

---

## 3. Criterio liviano vs pesado (operativo)

- **Liviano:** termina en segundos. Smoke tests, lectura de archivos, edición/commit de docs y código, `git pull/push`. → **Local**.
- **Pesado:** procesa el dataset EURUSD 20Y (D1/H4/H1; ~139k barras H1) o corre TNA/backtests/walk-forward/experimentos grandes. → **Grok**.

---

## 4. Procedimiento para Grok

### A — Preparar entorno

```text
Trabajando en ICT 2.0 (repo github.com/vjack666/ict2.0). Es un motor de trading ICT/SMC
Python 3.11+. Necesito correr un proceso pesado sobre EURUSD 20Y. El dataset está en
data/raw/EURUSD/ o en datasets/eurusd_dukascopy_20y/ como snapshot versionado.
NO calcules PnL ni emitas entradas salvo que el plan/SDD de la tarea lo autorice
explícitamente. Devuélveme resumen, JSON detallado y evidencia de commit/dataset.
```

### B — Traer repo

```bash
git clone https://github.com/vjack666/ict2.0.git
cd ict2.0
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

### C — Verificar dataset

Verificar `datasets/eurusd_dukascopy_20y/SHA256SUMS` y `metadata.json` cuando la tarea use el snapshot 20Y. No sustituir silenciosamente el dataset por otro.

### D — Drivers canónicos actuales

**Funnel 20Y ya cerrado.** No volver a ejecutarlo salvo que una nueva evidencia o cambio de código lo requiera. La ejecución histórica usó el runner versionado:

```bash
python scripts/grok_run_funnel_20y_full.py
```

Ese runner orquesta FVG/OB + Sequence + MTF dense con `sample_every=100`. El artifact canónico es `reports/audits/experiments/fvg_ob/mtf_seq_funnel.json` y está protegido por assert CI. `audits/codigo/mtf_seq_funnel.py` contiene funciones canónicas, pero no debe confundirse con el orquestador pesado que produjo el artifact.

**TNA 20Y:** el trace estratificado ya tiene PASS de integridad; el behavioral/full-span sigue pendiente. El driver pesado actual es:

```bash
python scripts/tna_20y_parallel.py
```

No interpretar el PASS de trace como edge ni como autorización de backtest.

**Backtest / walk-forward:** bloqueado hasta cerrar la pila pre-backtest requerida.

### E — Entrega

Toda ejecución pesada debe devolver:

1. resumen de gates;
2. JSON/Markdown versionado;
3. commit/dataset/hash usados;
4. cualquier limitación de cobertura (p. ej. muestra estratificada vs full-span).

### F — Sincronización

```bash
git pull origin main
```

---

## 5. Estado de trabajos pesados

| Job | Estado | Fuente de verdad |
| --- | --- | --- |
| Funnel 20Y FVG/OB + Sequence + MTF | **CERRADO — PASS + GATE CI** | `reports/audits/experiments/fvg_ob/mtf_seq_funnel.json` + worklog 2026-08-20 |
| TNA temporal AHF/MTF — TRACE | **PASS estratificado** | `reports/audits/temporal/AUDITORIA_TEMPORAL_AHF_RESULT.json` |
| TNA temporal AHF/MTF — BEHAVIORAL/full-span | **PENDIENTE** | plan TNA + `scripts/tna_20y_parallel.py` |
| SEQUENCE × CONTEXT STATE | **INSUFFICIENT_N** | `reports/audits/experiments/sequential/exp_sequence_x_context_state_H1_20Y.json` |
| Backtest / Walk-forward | **BLOQUEADO** | requiere pila pre-backtest + Funnel + TNA aceptables |

---

## 6. Notas de datos y límites

- Dataset 20Y versionado: `datasets/eurusd_dukascopy_20y/` con SHA256/metadata.
- M5 permanece diferido; no es requisito para cerrar H1/H4/D1 del Funnel.
- AWS queda DESCARTADO; `scripts/aws/*` es referencia histórica.
- Los resultados de auditoría son integridad/estructura/navegación salvo que un experimento declare explícitamente otra métrica.

---

## 7. Señal para Hermes

Cuando un proceso supere ~60s locales o toque el dataset 20Y completo, Hermes lo marca PESADO y avisa: “toca correr X en Grok”. El usuario lo dispara allá; Hermes sincroniza y audita el resultado.
