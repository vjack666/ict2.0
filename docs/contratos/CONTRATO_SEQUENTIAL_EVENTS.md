# Contrato — Motor de eventos secuenciales

**Estado:** NORMATIVO (v1)  
**Módulo:** `engine/sequential_events.py`  
**Propósito:** reemplazar la co-ocurrencia de flags por una **cadena temporal** de eventos ICT.

## Cadena canónica

```text
LIQUIDITY_POOL (EQH/EQL)
  → SWEEP
  → DISPLACEMENT
  → STRUCTURE (BOS-lite v1)
  → OB
  → FVG
  → RETEST
```

Cada etapa ocurre en una barra **estrictamente posterior** a la anterior.

## Qué NO es

- No es señal de entrada automática.
- No calcula PnL.
- No sustituye al bias HTF canónico del motor (v1 no usa EMA).
- STRUCTURE en v1 es BOS-lite (cierre más allá del último swing confirmado), no el `BOSTool` completo.

## Anti-look-ahead

- Pivots EQH/EQL confirmados solo con `left` velas a cada lado **ya cerradas**.
- Detección barra a barra; no se usa información futura para abrir/avanzar cadenas.
- Tests: orden de etapas, barras no decrecientes, humo en OHLC aleatorio.

## Configuración (`SeqConfig`)

Ventanas máximas entre etapas (barras): pool→sweep, sweep→disp, disp→struct, struct→OB, OB→FVG, FVG→retest.

## Salida

`list[SequentialChain]` con `nodes[]`, `status` ∈ {OPEN, COMPLETE, EXPIRED}, `summarize_chains()`.

## Gate v1

PASS si:

1. tests unitarios en verde;
2. ejecución H1 20Y sin crash;
3. `COMPLETE` implica las 7 etapas en orden;
4. documentación + evidencia JSON versionada.

## Evidencia inicial H1 20Y

Ver `reports/audits/experiments/sequential/sequential_events_H1_20Y.json`.

Interpretación: el embudo es deliberadamente estrecho; la mayoría de cadenas expiran en POOL o SWEEP. Eso es coherente con “secuencia ≠ flags”.
