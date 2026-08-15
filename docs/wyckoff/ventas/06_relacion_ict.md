# 06 — Cruce distribución Wyckoff ↔ ICT/SMC (v2)

| Campo | Valor |
|-------|-------|
| **Versión** | 2.0 |
| **Fecha** | 2026-07-12 |
| **Métricas** | [METRICS_CANON](../../METRICS_CANON.md) |

---

## 0. Contrato operativo

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | Wyckoff HTF sugiere **distribución / markdown** (sesgo ventas) | Sí (contexto) |
| 2 | ICT LTF da **entrada short** de precisión | Sí |
| 3 | Conflicto ICT alcista + Wyckoff bajista → no forzar | Sí |
| 4 | Killzone para el trigger M15 | Recomendado |

---

## 1. Mapeo distribución → ICT

| Wyckoff | Equivalente ICT / SMC |
|---------|----------------------|
| BC / UTAD | Sweep **BSL** + rechazo |
| UT/UTAD fallido | CHoCH/MSS **bajista** |
| SOW | **BOS** bajista |
| LPSY | **Order Block** / re-distribución |
| Phase B (rango) | PO3 fase **A** (construcción de causa; no confundir con “Distribution” del nombre de fase de venta) |
| UTAD (trampa arriba) | PO3 fase **M** Manipulation |
| Markdown | PO3 fase **D** expansión bajista + tendencia ICT |

> Corrección v2: Phase B **no** es “PO3 Distribution”. Phase B es rango (causa).  
> La **distribución Wyckoff** del esquema completo culmina en markdown; en lenguaje PO3 eso es expansión (D) tras manipulación (UTAD).

---

## 2. Sinergia operativa

1. **D1/H4:** PSY→BC→UTAD→SOW→LPSY → sesgo bajista.  
2. **M15:** sweep BSL + CHoCH/BOS short + FVG/OB.  
3. Killzone London/NY.  
4. Sin trigger ICT → observar.

---

## 3. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| Agente | `agents/wyckoff_agent.py` | Sobrecompra / UTAD vía stochastic exhaustion |
| ICT | `agents/ict_agent.py` | Short setups |
| Decisión | orchestrator / Decision | conflict_penalty |
| Fase | `scripts/fase_wyckoff_m15.py` | UI |
| Libros ICT | `05`, `06`, `08` | Sweep, Turtle/PO3 short |

---

## 4. Checklist de aplicación

- [x] Exhaustion en sobrecompra  
- [ ] Labels de fase distribución en UI  
- [ ] Métricas alineación short  
- [ ] Shadow shorts solo con A+M+D o Turtle completo  

---

## En resumen

Wyckoff ventas = contexto de **descarga** institucional. ICT = sniper del short.  
v2 corrige el mapeo Phase B → PO3 y alinea el lenguaje con el libro 08.
