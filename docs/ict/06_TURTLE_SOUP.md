# ICT — Turtle Soup (reversión contra tendencia)

| Campo | Valor |
|-------|-------|
| **ID** | `06_TURTLE_SOUP.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 |
| **Estado** | Stable (docs) · Needs-code (`model="turtle"`) |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) |

---

## 0. Contrato operativo

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | Sesgo HTF claro (BULLISH o BEARISH) | Sí |
| 2 | Setup **opuesto** al sesgo (contratrend) | Sí |
| 3 | Sweep de liquidez del lado “tramposo” (SSL si long de giro, BSL si short) | Sí |
| 4 | Confirmación MSS/CHoCH o BOS de giro en LTF | Sí |
| 5 | Zona FVG/OB + RR ≥ 1:2 | Sí |

**Turtle completo** ≠ PO3: aquí **NO** hay alineación a favor del HTF.

---

## 1. Teoría

Reversión tras **falsa ruptura** de liquidez de TF mayor. El mercado “hace sopa” a quienes esperaban continuación: barre stops y gira.

---

## 2. Práctica del trader

1. HTF: marcar BSL/SSL.  
2. LTF: sweep.  
3. MSS/CHoCH en dirección del giro.  
4. Entrada en retorno a FVG/OB.  
5. SL más allá del sweep; TP liquidez opuesta HTF.

---

## 3. Algoritmo

```
counter = setup_dir != htf_bias_dir
ready = counter and sweep and (choch_or_bos_flip) and zone and rr_ok
```

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| Checklist | `ict_backtest/rules.py` `counter_trend=True` | Hoy mezclado en `intradia` |
| UI | `resumen_widget.py` score Turtle Soup | Etiqueta contratrend |
| Secuencia | `ict_backtest/sequence.py` | Modo counter_trend + CHOCH antes de BOS |

**Aplicación:** `evaluate(model="turtle")` separado de `po3` (R1/R4).

---

## 5. Auditoría

| ID | Estado |
|----|--------|
| #1/#2 críticos para MSS real | ✅ |
| Métricas aisladas Turtle | 🔴 R4 |

---

## 6. Resultados

[METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11).

---

## 7. Checklist de aplicación

- [ ] Modelo `turtle` separado en rules + UI  
- [ ] Backtest E3 solo Turtle + costos  
- [ ] No etiquetar Turtle como PO3  

---

## En resumen

Turtle Soup = reversión post-sweep contra el HTF. Documentado y parcialmente cableado; falta **separación y medición** respecto a PO3.
