# ICT — MSS, CHoCH y BOS (estructura de mercado)

| Campo | Valor |
|-------|-------|
| **ID** | `02_MSS_CHOCH.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 |
| **Estado** | Stable |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) §3 y §5 |

> Fuentes de respaldo: MQL5 arts. 15017/22249, FluxCharts, Alchemy Markets.  
> **Verdad:** `ict_backtest/market_structure.py`, `detectors/bos.py`, `detectors/choch.py`, auditoría #1/#2.

---

## 0. Contrato operativo

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | **BOS** = ruptura de swing **a favor** de la tendencia vigente, preferible por **cierre de cuerpo** | Sí (continuación) |
| 2 | **CHoCH** = primera ruptura del swing **contrario**, idealmente del nivel del **último BOS** | Sí (aviso de giro) |
| 3 | **MSS** = CHoCH + desplazamiento + (ideal) BOS de confirmación en la nueva dirección | Sí (reversión aceptada) |
| 4 | Swings solo tras `lookback` velas de confirmación (**sin look-ahead**) | Sí |
| 5 | LTF se lee **siempre** contra sesgo HTF (a favor / contra) | Sí |

**Secuencia canónica de giro:**  
`… BOS↑ (marea) → CHoCH↓ (aviso) → BOS↓ (confirmación) …`

---

## 1. Teoría — jerarquía

| Patrón | Señal | Implicación |
|--------|-------|-------------|
| **BOS** | Continuación | La tendencia sigue viva |
| **CHoCH** | Aviso temprano | Posible giro — **no** confirmación sola |
| **MSS / MSB** | Reversión fuerte | Nueva tendencia formándose |

Nomenclatura: ICT usa MSS; SMC genérico MSB.  
En SMC-SYSTEMS: **MSS ≈ BOS tras CHoCH con desplazamiento**.

### BOS
- Rompe swing en dirección de la tendencia.  
- Regla dura (MQL5): validar por **close**, no solo mecha.

### CHoCH
- En uptrend: rompe el HL del último BOS → LL.  
- En downtrend: rompe el LH del último BOS → HH.  
- Fake-out: mecha, vela chica, noticias → tratar con cautela.

### Secuencia BOS → CHOCH → BOS
1. BOS mantiene marea.  
2. CHOCH avisa giro rompiendo el swing del **último BOS**.  
3. BOS nuevo confirma el giro. Sin paso 3, operar CHOCH solo es agresivo.

```
uptrend:  BOS↑  BOS↑  …
                 └─ CHOCH↓ (rompe último HL del BOS↑)
                        └─ BOS↓  BOS↓  …  (nueva marea)
```

---

## 2. Práctica del trader

1. HTF (D1/H4): sesgo y PD arrays.  
2. LTF (M15/M5): BOS/CHoCH de timing.  
3. A favor = LTF alineado a HTF; contra = Turtle Soup.  
4. Preferir London/NY.  
5. Entrada típica: tras CHoCH + zona (FVG/OB), no en la mecha del break.

---

## 3. Algoritmo y riesgos

| Riesgo | Detalle | Mitigación en repo |
|--------|---------|-------------------|
| Look-ahead en swings | Ventana centrada expone pivote antes de tiempo | #1: ventana NO centrada + `shift(lookback)` |
| CHOCH = BOS | Copia literal | #2: rompe nivel del último BOS opuesto |
| Chart Shift | Solo visual MT5 | Backtest en datos crudos |
| Histórico corto | Pocos swings al inicio | A6: ≥3–4 años |
| Gate CHOCH→BOS | Puede filtrar de más | Default OFF en EURUSD naive (METRICS §5) |

Apps de referencia: Market Structure Sentinel (MQL5 22249), EA BOS (15017, bug futuro documentado en foro), XGBoost+SMC (22526) ≈ nuestro QualityFilter.

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| Estructura backtest | `ict_backtest/market_structure.py` | BOS/CHOCH real |
| Detectores | `detectors/bos.py`, `choch.py` | Pipeline / mapa |
| Confluencia | `signals/pipeline.py` | Pesos BOS 1.0, CHOCH 3.0; `filter_choch_bos_confirm` opcional |
| Secuencia | `ict_backtest/sequence.py` | En counter_trend exige CHOCH antes de BOS_DONE |
| UI | `resumen_widget.py` | A favor / contra |

Verificado: `up_choch = (close > last_bos_level) & (last_bos_dir == -1)` (patrón análogo bajista).

---

## 5. Auditoría (cierre de tesis)

| Hallazgo | Antes | Después | Impacto |
|----------|-------|---------|---------|
| #1 Look-ahead | Swing en fila del pico | Desde confirmación | PF cadena 2.003→**1.548** |
| #2 CHOCH=BOS | 0 filas distintas | CHOCH real | Giro genuino |
| Gate CHOCH+BOS | — | Cableado, default OFF | METRICS §5: no ayuda EURUSD naive |

**Conclusión:** edge existe pero es **más modesto y frágil** en OOS; no declarar robustez sin A6 + costos.

---

## 6. Resultados

- Cadena Capa 2/3: [METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11).  
- Gate: [§5](../METRICS_CANON.md#5-gate-chochbos-confirm-2026-07-12).

---

## 7. Checklist de aplicación

- [x] CHOCH real + swings sin look-ahead  
- [x] Gate opcional cableado  
- [ ] Re-medir gate en XAUUSD + costos  
- [ ] Reparar test preexistente `test_choch_differs_from_bos` si sigue rojo en entorno limpio  
- [ ] UI: mostrar paso de secuencia (BOS / CHOCH / BOS confirm)  

---

## En resumen

BOS mantiene, CHoCH avisa, MSS confirma. SMC-SYSTEMS ya corrigió los bugs que inventaban estructura. El 10/10 de **producto** es re-validar el gate de confirmación en más símbolos y con costos, sin volver a mezclar “aviso” con “confirmación”.
