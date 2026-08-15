# ICT — Order Blocks y Breaker Blocks

| Campo | Valor |
|-------|-------|
| **ID** | `04_ORDER_BLOCKS.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 |
| **Estado** | Stable |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) |

---

## 0. Contrato operativo

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | Última vela contraria al impulso con cuerpo grande (huella) | Sí |
| 2 | Followthrough: vela siguiente confirma desplazamiento | Sí |
| 3 | Entrada **después** de que el followthrough esté cerrado (no en la vela de huella sola) | Sí |
| 4 | Estado: active / invalidated / aged | Sí (calidad) |
| 5 | Breaker: OB roto que actúa en sentido opuesto tras cambio de estructura | Opcional |

**OB usable** = #1–#3 y status active (o none legacy).

---

## 1. Teoría

**Order Block:** última vela en contra antes del impulso institucional (zona de oferta/demanda residual).

- OB alcista = última bajista antes del rally → soporte.  
- OB bajista = última alcista antes de la caída → resistencia.

**Válido** si hubo barrido/liquidez, imbalance (FVG) y aún no está mitigado.  
**Breaker:** OB roto que se reutiliza al revés tras CHoCH/MSS.

---

## 2. Práctica del trader

1. Esperar retroceso al OB (o FVG del displacement).  
2. Confluencia ideal: OB + FVG + CHoCH.  
3. SL fuera del OB.  
4. HTF zona / LTF entrada.  
5. Preferir OB de killzone.

---

## 3. Algoritmo

```
ob_bull = bearish_candle & large_body & close[i+1] > high[i]
ob_bear = bullish_candle & large_body & close[i+1] < low[i]
# entrada solo en t >= i+1 cerrado
```

**Riesgo:** `shift(-1)` en detección es OK si la **entrada** no usa esa info en la misma barra de señal prematura.

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| Detector | `detectors/ob.py` | OB + `_track_ob_validity` |
| Pipeline | `signals/pipeline.py` | `filter_ob_fvg`, invalidación Item E |
| Backtest | `ict_backtest/*` | `ob_direction`, zona LTF |

---

## 5. Auditoría y huecos

| ID | Estado |
|----|--------|
| #1 swings | ✅ afecta cadena, no OB puro |
| `shift(-1)` followthrough | ⚠️ vigilar en cualquier nuevo filtro de entrada |
| Aislar OB en métricas | 🔴 R4 |

---

## 6. Resultados

[METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11).

---

## 7. Checklist de aplicación

- [x] Invalidación/envejecimiento  
- [ ] Test explícito “no entrar en barra de huella sin followthrough cerrado”  
- [ ] Breaker como evento ligado a CHOCH real  

---

## En resumen

OB = huella pre-impulso; Breaker = huella reciclada tras giro. Código sólido; falta disciplina de tests de timing y métricas aisladas.
