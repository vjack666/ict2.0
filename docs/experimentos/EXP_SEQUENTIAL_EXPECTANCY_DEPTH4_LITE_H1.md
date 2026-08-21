# EXP — Expectancy con SL/TP estructural en DEPTH≥4 @ BOS-lite (H1, rango acotado)

**Fecha:** 2026-08-21
**Estado:** **EJECUTADO — GATE PASS**
**Data:** EURUSD H1 Dukascopy 2019-01-01 → 2024-12-31 (36934 barras)
**Artefacto:** `reports/audits/experiments/sequential/sequential_expectancy_depth4_lite_H1.json`

---

## Hipótesis

Las cadenas secuenciales depth≥4 (POOL→SWEEP→DISPLACEMENT→STRUCTURE) ancladas al
close del BOS-lite, operadas con SL/TP ESTRUCTURALES (mecha del sweep / swing roto;
proyección medida del rango), muestran expectancy en R-multiples reales superior a
entradas aleatorias en FVG con la MISMA lógica de SL/TP.

## Diseño

- Motor: `run_sequential(structure_mode="lite")`, UNA llamada sobre el rango acotado
  (PIT-estable dentro del rango; deuda motor FULL-vs-PREFIX registrada en bitácora
  2026-08-20 — no afecta este diseño de una sola pasada).
- Unidad: cadena depth≥4; anchor = barra STRUCTURE; dirección = dirección de la cadena.
- Dedup por `(structure_bar, direction)`.
- SL estructural: long = min(mecha sweep low, swing low roto) − 0.0001;
  short espejo. Nunca ATR (`docs/ict/14_STOP_LOSS_ESTRUCTURAL.md`).
- TP estructural v1 (fallback sancionado): extremo opuesto del rango de la secuencia
  extendido por su altura (proyección medida). Limitación v1 documentada.
- Resolución: escaneo barra a barra desde la barra posterior al entry, horizonte
 200 barras → "open" (excluido del win-rate, contado aparte);
  empate intrabar SL+TP → pesimista (SL).
- Baseline: entradas aleatorias en FVG (mismo n), misma función de SL/TP
 (ventana de rango = mediana sweep→structure = 6 barras).
- Bootstrap agrupado por chain_id, 2000 remuestreos,
 seed 42. CIs Wilson para win-rate.

## Métricas

| Grupo | n | cerrados | open | Win-rate (Wilson95) | mean R | median R |
|--------|--:|---------:|-----:|--------------------|-------:|---------:|
| Tratamiento (depth≥4) | 215 | 211 | 4 | 54.5% (47.8-61.1%) | 0.2675 | 0.9983 |
| Baseline (FVG random) | 215 | 205 | 3 | 43.9% (37.3-50.7%) | 0.2277 | -1.0 |

- Δ win-rate (trat − base): **0.106**
- Δ mean R (trat − base): **0.0398**
- Bootstrap meanR CI tratamiento: `[0.10853835671321634, 0.43013234978245596]`
- Bootstrap meanR CI baseline: `[-0.17153821723811521, 0.8606063559720186]`

## Resultado

- Cadena total motor: 3478; depth≥4: 256 ({'EXPIRED': 234, 'COMPLETE': 22}).
- Trades válidos tras dedup/warmup: tratamiento 215, baseline 215.
- Gate global: **PASS**.

## Lectura correcta

1. Los R son GEOMETRÍA de niveles estructurales fijados en el entry; no incluyen
   spread, slippage ni comisión.
2. El TP es proyección medida (fallback v1), no liquidez HTF real: los niveles
   absolutos de R dependen de esa convención.
3. "open" se excluye del win-rate: si el horizonte truncara tendencias ganadoras,
   el WR reportado está sesgado a la baja; revisar n_open antes de interpretar.
4. El empate intrabar se resuelve pesimista: los WR aquí son el piso, no el techo.
5. Comparar contra baseline FVG-random controla geometría de riesgo, NO la tesis ICT:
   un Δ positivo indica que el ANCLAJE secuencial aporta, no que la narrativa sea cierta.

## Policy

```
DEPTH≥4 SEQUENTIAL + SL/TP estructural  =  objeto de estudio
DEPTH≥4 SEQUENTIAL + SL/TP estructural  ≠  señal de trading aprobada
```

## Gate

| Criterio | Umbral | Resultado |
|----------|--------|-----------|
| n tratamiento (cerrados) | ≥30 | 211 → PASS |
| n baseline | ≥30 | 215 → PASS |
| **Global** | ambos | **PASS** |
