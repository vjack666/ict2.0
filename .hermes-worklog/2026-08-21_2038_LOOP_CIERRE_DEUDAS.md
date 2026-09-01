# Bitácora — LOOP de recuperación: cierre de deudas A2 / C3 / P2-alt

**Fecha:** 2026-08-21 19:47–20:38 UTC-5
**Autor:** Hermes (jefe de laboratorio) — 3 micro-agentes en SERIE (concurrencia 1) con loop de recuperación ante rate-limit/truncamiento.
**Rama:** feature/a5-audit-datos (HEAD ff6ed31 tras commit de la serie B)
**Motor:** run_sequential (depth>=4, lite) + resolve_outcome, protocolo idéntico al lab base (SL estructural 2-términos, TP measured_projection, H4/D1 según experimento, horizonte 200, bootstrap 2000 seed 42, wilson 95%).

---

## Mandato del usuario
"Si hay alguna traba o algo falla, crea un loop para solucionar. Todo debe pasar en verde. No pares hasta terminar con los experimentos de laboratorio."

**Interpretación del jefe (para que 'verde' sea honesto, no p-hacking):**
- El loop reintenta SOLO fallas de infraestructura (rate-limit HTTP 429, max_iterations, timeout de API).
- Un FAIL mecánico LEGÍTIMO (gate no pasa por el dato, no por error) se RESPETA y no se reintenta.
- Un BLOCKED por falta de datos se intenta ampliar 1 vez; si no, honesto.
- Nunca se cambian parámetros tras ver resultado para forzar PASS.

---

## Ejecución del loop

| Deuda | Agente | Intentos | Veredicto | JSON en disco |
|---|---|---|---|---|
| A2 (TP liquidez HTF real) | A2-FIX | 1 ❌ truncado (sin escribir) → 2 ✅ | **FAIL** | EXP_A2FIX_raw/audit.json |
| C3 (OOS 2025) | C3-FIX | 1/4 ✅ (parquet extendido) | **FAIL** | EXP_C3FIX_raw/audit.json |
| P2-alt (HTF filtro estructura H4) | P2-ALT | 1 ❌ timeout truncado → 2 ✅ | **FAIL** | EXP_P2ALT_raw/audit.json |

Concurrencia máxima 1 en todo momento. Sin paralelismo (evitó el rate-limit que truncó B en intentos previos).

---

## Resultados (verificados en disco, no en resumen)

### A2-FIX — TP en liquidez HTF real (BSL/SSL H4/D1)
- Treatment: n=166, **mean_R = −0.3864**, WR 23.5%, IC [−0.569, −0.190]
- Baseline A1/B1 reproducido exacto: +0.250
- **Δ = −0.6364 R** → el TP HTF destruye el edge.
- Veredicto: **FAIL**. Lección: el TP de liquidez HTF es PIT-estable y EJECUTABLE, pero está demasiado lejos del anclaje LTF depth≥4 → cierra tarde/mal. No se usa HTF como salida.

### C3-FIX — OOS 2025 (extendido a parquet 2025-01..2026-08)
- n=34 (≥30 ✓), **mean_R = +0.111**, WR 47.1%, IC [−0.295, +0.533] → **incluye 0**
- Origen: parquet data/raw (NO canónico CSV Dukascopy) → `cross_origin_caveat=true` declarado en data_integrity.
- Δ vs in-sample A1/B1: −0.139 R.
- Veredicto: **FAIL**. Lección: el edge SOBREVIVE en punto fuera de muestra (+0.111) pero PIERDE significancia estadística (IC cruza 0). Edge real pero frágil OOS.

### P2-ALT — HTF como filtro de ESTRUCTURA H4 (no sesgo, no TP)
- n=116, **mean_R = +0.3402**, WR 59.5%, IC [0.128, 0.540] (gate propio PASÓ)
- Δ vs B1: **+0.0903 R**, IC95 [−0.045, +0.240] → **incluye 0** → `htf_aporta=false`
- Mapeo H4→H1 PIT-estable (lag ∈ [0,723]h, siempre ≥0, 0 fugas) verificado por probe `p2alt_h4_pit.json`.
- Veredicto: **FAIL (incremental)**. Lección: el filtro de estructura H4 sube expectancy de +0.250 a +0.340 y baja drawdown 6.23→4.93, pero al 95% NO se distingue de ruido de muestreo. No hay evidencia de información incremental.

---

## Veredicto final del laboratorio (15 exp base + 3 fixes = 18)

**Proposición P2 (¿HTF aporta?) — REFUTADA en TODAS sus formas probadas:**
1. Sesgo direccional D1/H4 (serie B): NO aporta (B2 daña, B3/B4/B5 IC cruza 0).
2. TP liquidez HTF (A2-FIX): DESTRUYE el edge (−0.39 R).
3. Filtro estructura H4 (P2-ALT): mejora en punto pero NO significativa (Δ IC incluye 0).

**Conclusión científica:** en EURUSD H1 depth≥4, el edge ICT vive 100% en el anclaje LTF. Cualquier intervención HTF (sesgo, TP, o estructura) o lo deja igual o lo daña. La tesis "HTF dirige, LTF ejecuta" queda **refutada como filtro de contexto** en este setup.

**Robustez (P3): PARCIAL.** El edge sobrevive costes (C4) y GBPUSD (C1), pero:
- Muere en XAUUSD (C2).
- Es inestable en el tiempo (C5: 2/4 ventanas walk-forward).
- Fuera de muestra 2025 pierde significancia (C3-FIX: +0.111, IC cruza 0).

**NO se promueve a señal de trading.** Ningún experimento del lab es aprobación de operación.

---

## Entregables
- `reports/audits/EXP_A2FIX_*.json`, `EXP_C3FIX_*.json`, `EXP_P2ALT_*.json` (raw+audit)
- Runners: `scripts/lab/experiments/exp_A2FIX_runner.py`, `exp_C3FIX_runner.py`, `exp_P2ALT_runner.py`
- Probes: `scripts/lab/experiments/_probe_p2alt_htf_pit.py`, `reports/audits/data/p2alt_h4_pit.json`
- Skill `ict-system-experiment-lab` parcheado con receta PIT H4→H1 (por el agente P2-ALT)
- Esta bitácora.

**Estado de los 18 experimentos:** A(5)+B(5)+C(5)+fixes(3) = 18 con veredicto en disco. Sin BLOCKED pendientes (A2/C3 originales resueltos como FAIL honestos; el único BLOCKED restante es el diseño viejo de A2 que el fix reemplaza).
