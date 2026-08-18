# Plan de Auditorías Pre-Backtest — ICT FVG/OB

**Estado:** ACTIVO / EJECUCIÓN OBLIGATORIA ANTES DE BACKTEST
**Última actualización:** 2026-08-18
**Implementación:** `audits/codigo/`

## 1. Objetivo

Demostrar que datos, semántica, causalidad, detectores, relaciones y distribución del motor son confiables antes de evaluar performance.

## 2. Secuencia obligatoria

```text
A0 Data Integrity
↓
A1 Schema / Canonical Data
↓
A2 Point-in-Time / Look-Ahead
↓
A3 Semantic / Contract
↓
A4 Detector / Metamorphic
↓
A5 Cross-Timeframe Alignment
↓
A6 Lineage / Causal
↓
A7 Funnel
↓
A8 Coverage / Regime / Concentration
↓
A9 Selection / Experiment Governance
↓
BACKTEST ELIGIBLE
```

No se permite saltar un Gate. Un Gate en `FAIL` bloquea el siguiente.

## 3. Implementación canónica

- `audits/codigo/audit_stack.py` — A0→A9.
- `audits/codigo/run_full_stack.py` — CLI reproducible.
- `audits/codigo/data_integrity.py` — A0.
- `audits/codigo/temporal.py` — A2.
- `audits/codigo/funnel.py` — contrato A7.
- `audits/codigo/fvg_ob_funnel.py` — Funnel real de FVG/OB sobre EURUSD H1/H4/D1 usando los detectores canónicos.

## 4. Regla de evidencia

La existencia del código no equivale a Gate PASS. Cada ejecución necesita evidencia CI o local reproducible, fingerprint del stack y worklog.

## 5. Funnel FVG/OB

La primera ejecución real disponible usa:

- EURUSD H1/H4/D1;
- dataset público `ejtraderLabs/historical-data`;
- normalización ×100000 → precio EURUSD;
- detector canónico FVG de tres velas;
- detector canónico OB huella + follow-through;
- IA desactivada;
- sin PnL ni backtest.

La relación FVG↔OB no se inventa: el runner reporta poblaciones separadas y marca como no auditada la confluencia hasta tener una regla de relación implementada. Esto evita falsos resultados de confluencia.

## 6. Cierre del stack

A0-A9 sólo puede declararse `PASS` cuando:

- no existen hallazgos CRITICAL/HIGH;
- no existen violaciones LOOK_AHEAD;
- los contratos son deterministas;
- A7 Funnel se ejecutó con evidencia real;
- A8/A9 no presentan blockers;
- el reporte y `.hermes-index.md` están sincronizados.

## 7. Backtest

`BACKTEST_BLOCKED` hasta cerrar el stack completo.

M5 permanece diferido y no puede utilizarse como evidencia hasta disponer de una fuente reproducible.
