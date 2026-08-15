# ICT — Fair Value Gaps (FVG)

| Campo | Valor |
|-------|-------|
| **ID** | `03_FVG.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 |
| **Estado** | Stable |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) |

---

## 0. Contrato operativo

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | Hueco de 3 velas: bullish `low[i] > high[i-2]` o bearish `high[i] < low[i-2]` | Sí |
| 2 | Velas **cerradas** (sin usar i+1 futuro para crear el FVG) | Sí |
| 3 | Estado de fill: unfilled / mitigated trackeable | Sí (calidad) |
| 4 | Uso como zona de entrada en **retroceso**, no chase del impulso | Sí (práctica) |

**FVG válido para entrada** = #1+#2 y preferible unfilled (#3).

---

## 1. Teoría

Un **FVG** es un desequilibrio: el precio se mueve tan rápido que deja un rango no negociado entre tres velas. El mercado tiende a **rellenar** ese hueco (mitigación).

- **Alcista:** low de vela 3 > high de vela 1.  
- **Bajista:** high de vela 3 < low de vela 1.  
- Si mechas se solapan → no hay gap real.

Suele acompañar displacement que confirma BOS/MSS y convive con Order Blocks.

---

## 2. Práctica del trader

1. Tras sweep, esperar FVG de desplazamiento.  
2. Entrar en retroceso al FVG (no en la ruptura).  
3. SL fuera del FVG; TP liquidez opuesta o ≥1:2.  
4. Multi-TF: HTF define zona; LTF da timing.  
5. Preferir FVG nacidos en killzone (`01`).

---

## 3. Algoritmo

```
fvg_bull = low[i] > high[i-2]
fvg_bear = high[i] < low[i-2]
# fill: precio posterior toca el rango del hueco
```

**Riesgos:** look-ahead con i+1; Chart Shift (solo visual); histórico corto en HTF.

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| Detector | `detectors/fvg.py` | `shift(2)`, mid, fill status |
| Pipeline | `signals/pipeline.py` | Proximidad OB+FVG (ATR) |
| Backtest | `ict_backtest/data_feed.py`, `sequence.py`, `rules.py` | `fvg_state`, zona LTF |

**Look-ahead:** el detector FVG es limpio (solo pasado). La calidad del setup depende de swings/BOS limpios (#1).

---

## 5. Auditoría y huecos

| ID | Estado |
|----|--------|
| #1 no aplica a FVG puro | ✅ |
| Aislar contribución FVG al PF | 🔴 R4 |
| Costos en corridas | ⚠️ METRICS |

---

## 6. Resultados

Cadena compartida: [METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11).

---

## 7. Checklist de aplicación

- [x] Detector sin look-ahead  
- [ ] Ablación “con/sin FVG” en backtest  
- [ ] UI: unfilled vs mitigated visible en mapa  

---

## En resumen

FVG = vacío que el precio rellena. En SMC-SYSTEMS se detecta bien; el trabajo restante es **medir su peso real** en el edge y mostrarlo claro en el observador.
