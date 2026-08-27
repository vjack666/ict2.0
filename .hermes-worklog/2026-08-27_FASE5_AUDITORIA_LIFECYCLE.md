# FASE 5 — Auditoría de Lifecycle (MEDIR, no programar)

- **Fecha:** 2026-08-27
- **Agente:** Hermes
- **Disparador:** Diagnóstico CEO — el sistema acumula objetos ICT sin resolver
  ("cementerio de líneas"); medir el problema antes de cualquier regla nueva.
- **Base:** `engine/detectors/fvg.py`, `engine/detectors/ob.py`,
  `backtest/market_state.py` (worktree Codex, FASE 4).

---

## 1. DIAGNÓSTICO DE CÓDIGO VERIFICADO (REGLA DE ORO)

- `engine/detectors/fvg.py:24-34` — cada FVG se crea `state=ObjectState.ACTIVE`,
  sin transición terminal. `ob.py` análogo.
- `backtest/market_state.py:137-169` (proyección FASE 4, read-only):
  - L137-143: activa FVG/OB por `tradable_time <= decision_time`.
  - L156-164: ÚNICA transición = `ACTIVE → PARTIALLY_MITIGATED` por touch.
  - L166-169: mueve a history **solo si `live[obj].is_terminal`** — pero NADIE
    llama `transition_to` terminal para FVG/OB en esta proyección.
  - Resultado: FVG/OB se acumulan en `live` para siempre. Confirmado.

## 2. AUDITORÍA (scripts/audit_fase5_lifecycle.py)

Reusa detectores canónicos (solo lectura), simula acumulado vela-a-vela IGUAL a
`build_market_state` (sin terminales), sobre EURUSD real (parquet M15/H1/H4/D1),
ventana 1500 barras por TF.

| TF  | creados | ACTIVE/vela p50 | ACTIVE/vela max | edad p50 | edad max | % TERMINAL | % PARTIAL | FVG solapados |
|-----|--------:|----------------:|----------------:|---------:|---------:|----------:|---------:|-------------:|
| D1  | 357 | 188 | 357 | 778 | 1495 | **0.0%** | 98.0% | 1474 |
| H4  | 356 | 178 | 356 | 748 | 1494 | **0.0%** | 97.2% | 1383 |
| H1  | 279 | 134 | 279 | 723 | 1473 | **0.0%** | 98.2% | 1206 |
| M15 | 352 | 180 | 352 | 774 | 1496 | **0.0%** | 98.0% | 1562 |

## 3. HALLAZGOS (EMPÍRICOS)

1. **0% terminal en todos los TF.** Ningún FVG/OB alcanza MITIGATED/INVALIDATED/
   EXPIRED/CONSUMED. El tablero nunca se limpia.
2. **Todos los objetos viven hasta el final** (edad max ≈ 1495 barras = toda la
   ventana). p50 ~750 barras.
3. **Densidad altísima:** p50 de 134-188 objetos ACTIVE por vela; máximo = todos
   los creados (~280-357) simultáneamente.
4. **Solapamiento masivo:** 1200-1562 pares de FVG cuyos rangos se cruzan por TF.
   Muchas "zonas" son redundantes/spurious.

## 4. IMPLICACIÓN PARA EDGE (conexión con EXP-WYCKOFF-ICT-01)

Esto explica POR QUÉ el edge es indemostrable hoy:

- **Todo está presente casi siempre** → la feature de "zona cercana" no separa
  buenos de malos casos (cualquier operación toca alguna FVG/OB por ruido).
- **Sin episodios limpios** → no hay `nació→evolucionó→confirmó→murió` para
  comparar ganadores vs perdedores.
- Paradoja: **visor con miles de objetos** vs **experimento con muy pocos
  episodios independientes** (EXP-WYCKOFF-ICT-01: 17/29/23/85).

La barrera de EXP-WYCKOFF-ICT-01 (`INSUFFICIENT_N`) es estadística; pero la
**discriminación visual** es arquitectónica: sin lifecycle terminal, el visor
no puede decir "esta zona SÍ importó".

## 5. SIGUIENTE PASO (propuesta CEO, NO ejecutado aún)

> **FASE 5 — Canonical Lifecycle Resolution**: definir cuándo cada objeto ICT
> (FVG/OB/liquidez) pasa a terminal (MITIGATED por cierre a través de la zona;
> INVALIDATED por estructura rota; EXPIRED por edad; CONSUMED por setup AHF).
> Requiere decisión de diseño + autorización de modificar `engine/`/`backtest/`
> (fuera de alcance sin tu OK). Antes de programar, este reporte MIDE el problema
> objetivamente: `CREATED≈mucho, ACTIVE≈mucho, PARTIAL≈bastante, TERMINAL≈0`.

## 6. SALVAGUARDAS

- `can_train=false`, `can_trade=false`.
- Auditoría solo-lectura; no modifica `engine/`, `backtest/`, datasets.
- Sin backtest ni promoción.
