---
name: ict-topdown-pipeline-verification
description: Orquesta el motor ICT SYSTEM completo (Capa 1 HTF bias + Capa 2 secuencia A7 + Capa 3 fine execution SL/TP) sobre datos Dukascopy M15, con verificación de tesis ICT libro 18 y brechas documentadas. Incluye patrones de agentes paralelos, verificación con datos reales y protocolo de resultado con win-rate.
version: 1
author: Hermes
license: proprietary
metadata:
  hermes:
    tags: [ict, trading, funnel, sequence, execution, backtest, verification, dukascopy]
    related_skills: [ict-system-engine-workflow, smc-funnel-sequence-audit, trading-backtest-offline-verification]
---

# ICT Top-Down Pipeline Verification (Capa 1 + A7 Funnel + Fine Execution)

Clase: **verificación del pipeline ICT con datos reales** — no es solo auditoría
(sin P&L, como `smc-funnel-sequence-audit`) ni solo ejecución (como
`execution.py`). Es la orquestación de 3 capas con datos reales (Dukascopy M15
2006-2010), midiendo si el motor respeta la tesis ICT libro 18 y documentando
cada brecha con evidencia de código.

## Señal de uso (cuando crear/agregar)
- El usuario pide "ver el encadenamiento gate top-down" o "correrlo con datos" o
  "que el motor calcule SL/entry según la tesis".
- También cuando hay una corrección implícita del usuario sobre el modo de trabajo:
  modo CEO/autónomo (sin preguntar cada paso), con multiversos de hipótesis,
  agentes paralelos y resultado respaldado por datos reales.

## Estado aprendido (2026-09-02, datos 2006-2010)
El pipeline se verificó con datos del primer año (`datasets/eurusd_dukascopy_intraday_2006_2010/`). Resultado real:

```
Capa 1 (Bias HTF):     OK  → D1/H4/H1 → BULLISH/BEARISH/NEUTRAL detectado
Capa 2 (A7 Funnel):    PARCIAL → `run_sequence` requiere `est_htf_fn`
                         (patrón: `backtest/replay.py::htf_at`)
Capa 3 (Fine Exec SL): OK  → `execution.py`: SL = sweep - 0.3*rng, TP = RR 1:3
```

Datos confirmados por manifest (`eurusd_dukascopy_intraday_2006_2020_manifest.json`):
60 archivos mensuales (12 × 2006, 2007, 2008, 2009, 2010 + 2011-2020).
El archivo `raw/EURUSD_M15_2006.csv.csv` tiene solo 392 velas (5 días); los
meses completos están en `raw_monthly/`.

## Hipótesis (multiversos) y evidencia
- **H1 (SL/TP libro 18)**: `engine/execution.py` cumple. SL: `sweep - 0.3*rng_exec`
  (`l99-111`, fallback `sl_v` si no hay sweep). TP: `entry ± rr*(entry-sl)` (`l133`, `l163`).
  Buffer: `STRUCT_SL_BUFFER_RANGE=0.3` (`l32`). Cita contrato: `engine/sequence.py:14-17`
  ("SL estructural SIEMPRE en el TF más fino"). ✓ 8/8 puntos de auditoría.
- **H2 (datos)**: `raw_monthly/2006/` confirma 12 CSVs; manifest con SHA-256. ✓
- **H3 (replay)**: `backtest/replay.py::run_visual_replay` es el patrón canónico; `htf_at`
  (`l453-463`) es la función `est_htf_fn` que falta en el script demo.
- **H4 (Silver Bullet)**: `engine/silver_bullet.py:45-81`; usa `killzone.py:25-31`.
  `hard_filter=False` por defecto (`l105`) → señales fuera de killzone NO se descartan.
- **H5 (win rate)**: `engine/sequential_outcome.py:92-129` (`resolve_outcome`) calcula
  `TP`/`SL` con rango y `OutcomeConfig.horizon_bars=200` por defecto.

## Brechas documentadas (sin inventar fixes)
No se parcheó código del motor. Las brechas son reales y documentadas:
1. `execution.py` es módulo de geometría pura — NO filtra killzone (correcto por contrato,
   no error).
2. `silver_bullet.flag_silver_bullet` con `hard_filter=False` (por defecto) no descarta
   señales fuera de London/NY; para medir 60% win rate, se requiere conectar el filtro SB
   antes de contar señales.
3. `run_sequence` requiere `est_htf_fn`; el script `demo_topdown_gate.py` fallaba sin él.
   La solución es usar `replay.py` (que lo provee) en lugar de llamar `run_sequence`
   directamente.
4. `demo_quick.py` (verificado) cubre solo M15 + estructura; `demo_topdown_gate.py`
   cubre Capa 1 + estructura; para Capa 3 completa con P&L, se debe ejecutar
   `run_visual_replay` con datos completos.

## Artefactos verificados (no inventados)
- `scripts/demo_quick.py` — ejecutado con `.venv/Scripts/python.exe`, resultado real.
- `reports/` — CSV generado con tiempo, direction, entry/sl/tp/rng/buffer.
- `scripts/demo_topdown_gate.py` — creado para pipeline completo (Capa 1 + 2 + 3).

## Regla operativa (captura de preferencia del usuario)
- **Modo autónomo**: ejecutar sin preguntar pasos intermedios (`autónomo sin preguntar`).
- **Verificación real**: cada afirmación respaldada con código real o datos (no simulación).
- **Bitácora detallada**: cada paso documentado en archivo (`.hermes-index.md` o `reports/`).
- **Multiversos con agentes paralelos**: usar `delegate_task` cuando hay 3+ subproblemas.
- **No autocertificar PASS**: si un paso queda INCONCLUSIVE, no transformar a PASS; arreglar la raíz.

Ver `references/ict_pipeline_brechas.md` para las citas exactas de líneas, el archivo
`references/htf_bias_quality.md` para la receta de calidad HTF, y `references/funnel_density_filters.md`
para los filtros de densidad (Ley 16).
