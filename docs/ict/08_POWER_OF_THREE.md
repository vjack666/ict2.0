# ICT — Power of Three (PO3 / AMD) — pasado · presente · futuro

| Campo | Valor |
|-------|-------|
| **ID** | `08_POWER_OF_THREE.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 / RFC-001 |
| Estado | Stable (docs) · **A/M/D implementado (R1 2026-07-13)** |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) |
| **Roadmap** | R1 prioritario — [ROADMAP_BIBLIOTECA_Y_APLICACION](../plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md) |

> **Fuente de verdad:** este contrato + código futuro `po3_state` + `ict_backtest/rules.py`.  
> PO3 es el libro del **ciclo del trade en el gráfico**: lo que ya pasó, lo que está pasando y lo que se espera que pague.

---

## 0. Contrato operativo — fases A / M / D

| Tiempo del gráfico | Fase | Condición medible | Obligatorio |
|--------------------|------|-------------------|:-----------:|
| **Pasado** | **A — Accumulation** | Sesgo HTF (D1 o H4) ∈ {BULLISH, BEARISH} **o** rango explícito con high/low de sesión/Asian marcados | Sí |
| **Presente** | **M — Manipulation** | Sweep de liquidez **en contra** del sesgo (caza de stops) con ruptura + cierre de vuelta (regla sweep de `05`) | Sí |
| **Futuro** | **D — Distribution / expansión** | CHoCH o BOS **a favor** del sesgo **después** del sweep + zona de entrada FVG u OB en LTF | Sí |
| Gestión | RR | SL fuera del extremo de manipulación; TP ≥ 1:2 o liquidez opuesta | Sí |
| Dirección | A-favor | `direction` del setup **alineada** al sesgo HTF (si no → es Turtle Soup, no PO3) | Sí |

### Definiciones de estado

```
po3.complete  = A and M and D and aligned
po3.direction = LONG | SHORT | NEUTRAL
po3.incomplete_reason = lista de fases faltantes
```

| Estado | Significado en UI |
|--------|-------------------|
| `complete=True` | **PO3 listo** — ciclo cerrado; candidato a entrada |
| Solo A | Contexto listo; esperar manipulación |
| A+M sin D | Trampa hecha; esperar expansión / CHoCH |
| M sin A | Sweep sin sesgo → no etiquetar PO3 |
| Alineación fallida | Puede ser Turtle Soup (`06`) |

**Regla dura:** score alto sin `complete` **no** es entrada PO3.

---

## 1. Teoría

El **Power of Three (PO3)** / modelo **AMD** describe por qué el precio suele:

1. **Acumular** (construir causa / rango / sesgo),  
2. **Manipular** (barrer liquidez en falso),  
3. **Distribuir / expandir** (movimiento real que paga).

Es la “réplica” del ciclo en el gráfico:

| Fase | Lectura humana |
|------|----------------|
| A | “¿Dónde se construyó el interés?” (pasado) |
| M | “¿Dónde cazaron stops ahora?” (presente) |
| D | “¿Hacia dónde se expande el movimiento?” (futuro del trade) |

No es un patrón de una sola vela: es un **relato de secuencia**.

---

## 2. Práctica del trader

1. **Sesgo del día** en D1/H4 (o rango del día / open).  
2. Marcar **open del día** y liquidez Asian si aplica.  
3. Esperar **manipulación** más allá del open/rango (sweep).  
4. Confirmar en M15/M5 con **CHoCH/BOS a favor** + FVG/OB.  
5. SL fuera del extremo de M; TP en liquidez opuesta o ≥1:2.  
6. Preferir killzone London/NY (`01`).

**PO3 ≠ Turtle Soup:** PO3 es **continuación a favor** tras la trampa.  
Turtle Soup es **reversión contra** el HTF (`06`).

---

## 3. Algoritmo

```
A = has_htf_bias OR has_session_range
M = recent_sweep AND sweep_opposes_bias
D = (choch_or_bos_with_bias) AND (fvg_or_ob_zone) AND after(M)
aligned = setup_dir == bias_dir
complete = A and M and D and aligned
```

**Riesgos**

| Riesgo | Mitigación |
|--------|------------|
| Marcar D antes de confirmar swing | Solo velas cerradas; fix #1 |
| CHOCH = copia de BOS | Fix #2 — CHOCH real |
| Mezclar con contratrend | Flag `aligned` obligatorio |
| Look-ahead en open del día | Open = precio de la vela de apertura ya cerrada / known |

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol hoy |
|-------|------|---------|
| Sesgo / trend | motor observador, `trend_context` | Fase A parcial |
| Sweep | `bos.py` + `pipeline.py` / flags estructura | Fase M |
| CHoCH/BOS | `choch.py`, `bos.py` | Fase D parcial |
| FVG/OB | `fvg.py`, `ob.py` | Zona D |
| Score UI | `resumen_widget.py` → `modelo_ict` PO3 | Score suelto, **no** `complete` |
| Checklist | `rules.py` `checklist_intradia` | Mezcla PO3 + Turtle |
| Target | `signals/po3.py` (pendiente R1) | Estado A/M/D canónico |

**Hoy:** PO3 es **narrativa + puntos**.  
**Óptimo (R1):** `po3_state` + `evaluate(model="po3")` importado por UI y backtest.

---

## 5. Auditoría y huecos

| ID | Tema | Estado |
|----|------|--------|
| #1 | Look-ahead en swings afectaba “D” | ✅ Fix |
| #2 | CHOCH real necesario para D genuino | ✅ Fix |
| #5 | WF pasado→futuro | ✅ Fix dirección |
| PO3-1 | No hay `complete` A/M/D en código | ✅ R1 (`signals/po3.py`) |
| PO3-2 | Open del día no es filtro duro | ✅ R3 (`signals/po3.py`: `compute_session_open` + filtro duro en M) |
| PO3-3 | No hay métricas **aisladas** de PO3 | 🔴 R4 |
| PO3-4 | Mezcla con Turtle en `intradia` | ✅ R1.2 (`evaluate(model="po3")` separado) |

---

## 6. Resultados

PO3 participa de la cadena intradía; **no** tiene aún fila propia aislada.  
Ver [METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11) (Capa 2/3, edge frágil).  
Tras R4, añadir § “PO3 only” en METRICS_CANON.

---

## 7. Checklist de aplicación al sistema
- [x] Implementar `po3_state` (A/M/D/complete/direction) — `signals/po3.py`
- [x] `evaluate(model="po3")` separado de Turtle Soup — `ict_backtest/rules.py`
- [x] UI: "PO3 listo" vs "falta M/D" — `app_observador/ui/resumen_widget.py`
- [ ] Mapa o labels: A / M / D (R2+ visual)
- [ ] Backtest solo-PO3 + costos → METRICS_CANON (R4)
- [ ] Shadow en diario ("hubiera entrado PO3") (R5)
- [x] Tests sintéticos sin look-ahead — `tests/test_po3.py`
- [x] Open del día como filtro duro de M (`session_open` + `broke_open`) — R3 `signals/po3.py`

---

## En resumen

PO3 es el libro de **pasado (A) → presente (M) → futuro (D)** del movimiento.  
La documentación 10/10 fija el **contrato `complete`**.  
El sistema óptimo nace cuando ese contrato es **código único** en observador y backtest, medido en OOS con costos — no cuando el score “parece” PO3.
