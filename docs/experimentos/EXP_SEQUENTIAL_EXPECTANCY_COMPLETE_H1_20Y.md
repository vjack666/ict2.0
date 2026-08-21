# EXP — Expectancy en cadenas secuenciales COMPLETE (H1 20Y)

**Fecha:** 2026-08-18  
**Estado:** **EJECUTADO — MUESTRA INSUFICIENTE (n=5)**  
**Entrada:** cierre de la barra de **RETEST** (secuencia ya COMPLETE)  
**Data:** EURUSD H1 Dukascopy 2006–2025  
**Artefacto:** `reports/audits/experiments/sequential/sequential_expectancy_COMPLETE_H1_20Y.json`

---

## Embudo del motor

| Total cadenas | COMPLETE | Scored |
|--------------:|---------:|-------:|
| 1.460 | **5** | 5 |

De las 5, **2 comparten el mismo `retest_bar`** (24743) → no son independientes.

---

## Tabla (end>0 tras RETEST)

| Bucket | n | +6 | +12 | +24 | +48 | +96 |
| -------- | --: | ----: | ----: | ----: | ----: | ----: |
| COMPLETE_ALL | 5 | 20 % | 0 % | 80 % | 80 % | 80 % |
| COMPLETE_BULL | 2 | 0 % | 0 % | 50 % | 50 % | 50 % |
| COMPLETE_BEAR | 3 | 33 % | 0 % | 100 % | 100 % | 100 % |
| BASELINE_RANDOM_FVG | 100 | 51 % | 50 % | 61 % | 58 % | 54 % |

`expectancy_price` (+24) COMPLETE_ALL ≈ **+0.0043** (media del movimiento firmado).  
Baseline FVG aleatorio ≈ **+0.0008**.

**No interpretar como edge validado:** con n=5 cualquier % es ruido.

---

## Lectura correcta

1. El motor **sí produce** secuencias completas medibles (existencia).
2. La tasa de completitud es **extremadamente baja** (5 / 1460 ≈ 0.3 %).
3. Los números de win-rate/expectancy en COMPLETE **no tienen potencia estadística**.
4. `mean_R` está inflado cuando MAE es casi 0 (no hay stop fijo de sistema).
5. Comparar 80 % (n=5) vs 61 % baseline (n=100) **no** autoriza desplegar entradas.

---

## Política

```text
COMPLETE chain  =  objeto de estudio
COMPLETE chain  ≠  señal de trading aprobada
```

Siguiente trabajo útil:

- relajar STRUCTURE (BOS/CHOCH canónico) o ventanas para subir n de COMPLETE **sin** volver a flags;
- o medir expectancy en profundidad ≥ 4–5 (aunque no lleguen a RETEST);
- definir stop/target fijos antes de hablar de R reales.

---

## Gate

| Criterio | Resultado |
| ---------- | ----------- |
| Medición ejecutada | Sí |
| n suficiente para edge | **No** |
| Hipótesis “COMPLETE ⇒ edge” | **No contrastable aún** |
