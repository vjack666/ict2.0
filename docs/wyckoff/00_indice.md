# Biblioteca Wyckoff — Índice (v2 · 10/10)

Colección del **Método Wyckoff** (Richard D. Wyckoff) para SMC-SYSTEMS.

Wyckoff describe cómo el *Composite Operator* acumula y distribuye. Es **complementario a ICT**:  
- **Wyckoff** → contexto HTF (¿compran o venden?).  
- **ICT** → entrada LTF (¿dónde y cuándo?).  

En código: `agents/wyckoff_agent.py` + `agents/ict_agent.py` + Decision Agent  
(pesos tipicos: ICT 0.35 / Wyckoff 0.30 / Structure 0.20 / ML 0.15).

> Fuentes: Wyckoff Analytics, BitMEX Research, TrendSpider Education (público).  
> Rulebook operativo: `docs/reglas/WYCKOFF_RULEBOOK.md` (o `docs/WYCKOFF_RULEBOOK.md` si aplica).  
> Métricas de sistema: [METRICS_CANON](../METRICS_CANON.md).  
> Aplicación: [ROADMAP_BIBLIOTECA_Y_APLICACION](../plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md).

## Estructura

| Carpeta | Tema |
|---------|------|
| [`compras/`](compras/00_indice.md) | Acumulación / buy-side / markup |
| [`ventas/`](ventas/00_indice.md) | Distribución / sell-side / markdown |

Cada libro de cruce `06_relacion_ict.md` tiene **mapeo a código** y checklist de aplicación.

## Estándar 10/10 (Wyckoff)

Todo libro debe poder responder:

1. ¿Qué fase/evento es?  
2. ¿Cómo se ve en precio/volumen?  
3. ¿Equivalente ICT?  
4. ¿Dónde lo toca SMC-SYSTEMS?  
5. ¿Qué falta cablear?  

## Orden de lectura

1. `compras/01` o `ventas/01` (leyes)  
2. Fases A–E  
3. Eventos + volumen  
4. Operar  
5. **Cruce ICT** (`06`)  
6. Biblioteca ICT `08` PO3 (mismo ciclo, otro lenguaje)  
