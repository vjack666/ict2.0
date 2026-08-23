# Estrategia de ejecución — ICT 2.0

**Decisión vigente:** 2026-08-23 (Ruben)
**Estado:** VIGENTE — ejecución exclusivamente local en el PC de Ruben
**Responsable de ejecución:** PC local de Ruben; no se usa GitHub Actions ni otra nube

---

## 1. Regla general

| Tipo de proceso | Dónde se ejecuta | Quién lo dispara |
| --- | --- | --- |
| Experimentos, tests, auditorías, backtests, walk-forward y jobs de laboratorio | **Local** — PC de Ruben | Hermes, con autorización del alcance correspondiente |
| Git, revisión, historial y publicación de cambios | **GitHub como repositorio** | Usuario/Codex, según autorización explícita |

**Regla local-only.** Ningún experimento, test, auditoría, backtest, descarga de datos ni job de laboratorio se ejecuta en GitHub Actions, Grok, AWS u otra nube. Si el PC no puede completar el trabajo, el estado es `WAITING`/`BLOCKED` y se informa al usuario; no se migra automáticamente a la nube.

La evidencia histórica producida antes de esta decisión conserva su valor documental, pero no autoriza nuevas ejecuciones cloud ni cambia la regla vigente.

---

## 2. Por qué (traza)

- Se evaluó AWS EC2 `t4g.small` y se **descartó EC2**.
- Evidencia del benchmark local (`reports/audits/benchmark_spayk.json`, host `spayk`, 20 cores / 16.8 GB): A0-A9 audit ~0.12 s; AHF_TEMPORAL serial llegó a timeout de 1800 s antes del parche de navegación.
- El motor `engine/mtf_navigation.py` recibió posteriormente una optimización O(n) de precompute; la regresión publicada reporta equivalencia bit-exact frente al motor anterior en 600 layer-checks.
- La decisión del 2026-08-23 reemplaza el canal cloud anterior: toda ejecución futura debe quedar trazada al PC local.
- Ver `docs/AWS_EXECUTION_HOST.md` (marcado **DESCARTADO**) para la traza completa de la evaluación AWS.

---

## 3. Criterio liviano vs pesado (operativo)

- **Liviano:** termina en segundos. Smoke tests, lectura de archivos, edición/commit de docs y código, `git pull/push`. → **Local**.
- **Pesado:** procesa el dataset EURUSD 20Y (D1/H4/H1; ~139k barras H1) o corre TNA/backtests/walk-forward/experimentos grandes. → **PC local**, con progreso/heartbeat y evidencia persistida.

---

## 4. Protocolo local obligatorio

### A — Preparar y verificar el entorno

```powershell
git status --short
git rev-parse HEAD
C:\Python314\python.exe --version
C:\Python314\python.exe -m pytest tests -q
```

El experimento debe ejecutarse desde el checkout local autorizado, con el commit,
dataset y dependencias registrados antes de iniciar. No se clonan repositorios ni
se instalan dependencias en un runner cloud para ejecutar el trabajo.

### B — Verificar dataset

Verificar `datasets/eurusd_dukascopy_20y/SHA256SUMS` y `metadata.json` cuando la tarea use el snapshot 20Y. No sustituir silenciosamente el dataset por otro.

### D — Drivers canónicos actuales

**Funnel 20Y ya cerrado.** No volver a ejecutarlo salvo que una nueva evidencia o cambio de código lo requiera. La ejecución histórica usó un runner versionado cuyo nombre conserva `grok`; cualquier revalidación autorizada se ejecutará localmente:

```powershell
C:\Python314\python.exe scripts/grok_run_funnel_20y_full.py
```

Ese runner orquesta FVG/OB + Sequence + MTF dense con `sample_every=100`. El artifact canónico es `reports/audits/mtf_seq_funnel.json` y conserva un assert histórico; no debe ejecutarse en CI. `audits/codigo/mtf_seq_funnel.py` contiene funciones canónicas, pero no debe confundirse con el orquestador pesado que produjo el artifact. Las referencias a CI en documentación antigua describen evidencia histórica, no un host permitido.

**TNA 20Y:** el trace estratificado y el behavioral/full-span streaming tienen PASS de integridad. El artefacto cerrado de esta etapa es:

```text
reports/audits/tna_streaming_prefix_2026-08-22.json
```

El driver pesado histórico sigue disponible para una revalidación autorizada:

```powershell
C:\Python314\python.exe scripts/tna_20y_parallel.py
```

No interpretar ningún PASS de integridad como edge ni como autorización de backtest.

**Ejecución congelada:** `docs/planificacion/EXECUTION_FREEZE_2026-08-22.json`; cubre intradía M15, no M5/M1/scalping.

**Backtest / walk-forward:** requiere decisión explícita del cliente después del cierre de la pila; no se dispara automáticamente.

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

`git pull`/`git push` solo sincronizan código y evidencia autorizada; no deben
disparar jobs remotos. Los workflows históricos de GitHub están desactivados.

---

## 5. Estado de trabajos pesados

| Job | Estado | Fuente de verdad |
| --- | --- | --- |
| Funnel 20Y FVG/OB + Sequence + MTF | **CERRADO — PASS + GATE CI** | `reports/audits/mtf_seq_funnel.json` + worklog 2026-08-20 |
| TNA temporal AHF/MTF — TRACE | **PASS estratificado** | `reports/audits/AUDITORIA_TEMPORAL_AHF_RESULT.json` |
| TNA temporal AHF/MTF — BEHAVIORAL/full-span | **PASS local / gate PASS** | `reports/audits/tna_streaming_prefix_2026-08-22.json` |
| A0-A9 full-stack | **PASS local + evidencia CI histórica** | `reports/audits/A0_A9_audit_stack.json` + worklog de cierre |
| Ejecución congelada | **PASS M15 / limitado** | `reports/audits/execution_freeze_2026-08-22.json` |
| SEQUENCE × CONTEXT STATE | **INSUFFICIENT_N** | `reports/audits/exp_sequence_x_context_state_H1_20Y.json` |
| Backtest / Walk-forward | **REQUIERE DECISIÓN EXPLÍCITA** | gates locales PASS; sin autorización automática |

---

## 6. Notas de datos y límites

- Dataset 20Y versionado: `datasets/eurusd_dukascopy_20y/` con SHA256/metadata.
- M5 permanece diferido; no es requisito para cerrar H1/H4/D1 del Funnel.
- AWS, Grok y GitHub Actions quedan fuera de la ejecución vigente; cualquier referencia cloud es histórica.
- Los resultados de auditoría son integridad/estructura/navegación salvo que un experimento declare explícitamente otra métrica.

---

## 7. Señal para Hermes

Cuando un proceso supere ~60s locales o toque el dataset 20Y completo, Hermes lo
marca PESADO, mantiene la ejecución en el PC local y exige progreso/heartbeat,
artefactos y evidencia reproducible. Si no puede continuar localmente, informa
`WAITING`/`BLOCKED`; nunca propone Grok, GitHub Actions, AWS u otra nube como
ejecutor por defecto.
