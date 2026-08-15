# 06 — Cruce acumulación Wyckoff ↔ ICT/SMC (v2)

| Campo | Valor |
|-------|-------|
| **Versión** | 2.0 |
| **Fecha** | 2026-07-12 |
| **Métricas** | [METRICS_CANON](../../METRICS_CANON.md) |

---

## 0. Contrato operativo

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | Wyckoff HTF sugiere **acumulación / markup** (sesgo compras) | Sí (contexto) |
| 2 | ICT LTF da **entrada** (no reemplaza el contexto) | Sí |
| 3 | Conflicto ICT bajista + Wyckoff alcista → **no forzar** (conflict penalty) | Sí |
| 4 | Entrada M15 preferible en killzone | Recomendado |

---

## 1. Mapeo acumulación → ICT

| Wyckoff | Equivalente ICT / SMC |
|---------|----------------------|
| SC / Spring | Sweep **SSL** + rechazo |
| Spring + Test | CHoCH/MSS **alcista** |
| SOS (rompe AR) | **BOS** alcista |
| LPS | **Order Block** / re-acumulación |
| Phase B (rango) | PO3 fase **A** Accumulation (`docs/ict/08`) |
| Markup | Tendencia alcista post confirmación |

---

## 2. Sinergia operativa (rutina del proyecto)

1. **D1/H4 Wyckoff:** PS→SC→Spring→SOS→LPS → sesgo alcista.  
2. **M15 ICT:** sweep SSL + CHoCH/BOS long + FVG/OB.  
3. **Killzone:** `docs/ict/01_KILLZONES.md`.  
4. Si solo hay Wyckoff sin trigger ICT → **esperar** (no cazar).

---

## 3. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| Agente | `agents/wyckoff_agent.py` | Fases + stochastic exhaustion (SC/Spring) |
| ICT | `agents/ict_agent.py` | Voto estructura LTF |
| Decisión | `agents/orchestrator.py` / Decision Agent | Pesos + conflict_penalty |
| Fase M15 | `scripts/fase_wyckoff_m15.py` | Fase para observador |
| UI | observador sesgo / Lab Setup | Muestra alineación |
| Rulebook | `docs` Wyckoff rulebook | Reglas del agente |

---

## 4. Checklist de aplicación

- [x] Agente Wyckoff + stochastic exhaustion  
- [ ] Exponer fase A–E en UI con labels de este libro  
- [ ] Log de conflicto ICT/Wyckoff en black-box  
- [ ] Medir trades “solo alineados” vs “conflicto” (R4)  

---

## En resumen

Wyckoff compras = **por qué** el sesgo es long. ICT = **dónde** entrar.  
El sistema ya vota ambos; el 10/10 es **transparencia de conflicto** y métricas de alineación.
