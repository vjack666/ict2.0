# ICT — Liquidez (BSL / SSL) y Liquidity Sweeps

| Campo | Valor |
|-------|-------|
| **ID** | `05_LIQUIDEZ.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 |
| **Estado** | Stable (docs) · ✅ fuente única de liquidez unificada (R3 2026-07-13) |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) |

---

## 0. Contrato operativo

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | Nivel BSL = liquidez sobre máximos (stops de cortos) | Sí (mapa) |
| 2 | Nivel SSL = liquidez bajo mínimos (stops de largos) | Sí (mapa) |
| 3 | **Sweep:** rompe el nivel y **cierra de vuelta** adentro en la misma vela | Sí (filtro) |
| 4 | Entrada **después** del sweep (no en la mecha de caza) | Sí |
| 5 | Misma definición de sweep en mapa, pipeline y backtest | Sí (arquitectura) |

**Sweep válido** = #3 con swings confirmados sin look-ahead.

---

## 1. Teoría

El precio busca **liquidez** (stops agrupados).

- **BSL (Buyside):** sobre highs.  
- **SSL (Sellside):** bajo lows.  
- **Sweep:** rompe y revierte → manipulación (fase M de PO3).

---

## 2. Práctica del trader

1. Marcar BSL/SSL en HTF (y PDH/PDL).  
2. Esperar sweep.  
3. Confirmar (CHoCH/FVG) antes de entrar.  
4. No “pescar el cuchillo” en la ruptura.  
5. TP frecuente = liquidez opuesta.

Usos: Turtle Soup, Silver Bullet, PO3 (manipulación).

---

## 3. Algoritmo

```
bearish_sweep = (high > swing_high) & (close < swing_high)
bullish_sweep = (low  < swing_low)  & (close > swing_low)
```

Zonas BSL/SSL: cluster de swings en margen `atr/margin`.

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| Zonas | `detectors/liquidity.py` | **Pinta** BSL/SSL (docstring: no rutea trade) |
| Sweep señal | `detectors/bos.py` + `signals/pipeline.py` | **Filtra** entradas |
| Checklist | `ict_backtest/rules.py` | Exige sweep en intradía |

### Hueco de arquitectura (honesto)

```
liquidity.py  ──pinta──► mapa
bos/pipeline  ──filtra──► señal
```

La señal **sí** usa sweep; la “fuente de liquidez” visual **no** es la misma que el filtro.  
**Aplicación:** R3 — adapter único `liquidity_context`.

---

## 5. Auditoría

| ID | Estado |
|----|--------|
| Hueco pinta≠filtra | ✅ R3 (`detectors/liquidity_context.py`: `canonical_sweep` única fuente; `detect_bos` y `signals/pipeline.py` delegan) |
| #1 pivots | ✅ sin fuga en diseño actual |
| Prevalencia sweep ~66% M15 | ver METRICS §6 |

---

## 6. Resultados

[METRICS_CANON §3 y §6](../METRICS_CANON.md).

---

## 7. Checklist de aplicación
- [x] Unificar o envolver liquidez+sweep en un contexto  (R3: `detectors/liquidity_context.py`)
- [x] UI/backtest/pipeline usan la misma `canonical_sweep`  (`detect_bos` y `signals/pipeline.py` delegan)
- [x] Tests de definición única de sweep  (`tests/test_liquidity_context.py`)
- [ ] Mapa (`scripts/mapa_precio.py`) importar zonas BSL/SSL desde `build_liquidity_context` (pendiente KZ-2-like; no bloquea R3)
- [ ] `adapters/feature_enrichment_adapter._detect_liquidity_sweeps` (swing-based, para el agente) documentar como excepción señalada: usa swings, no prior-extreme; revisar en R3.5 si se unifica al agente

---

## En resumen

Liquidez = comida del mercado; sweep = manipulación. El sistema detecta sweeps útiles, pero debe **cerrar la doble fuente** (pintar vs filtrar) para quedar 10/10 también en arquitectura.
