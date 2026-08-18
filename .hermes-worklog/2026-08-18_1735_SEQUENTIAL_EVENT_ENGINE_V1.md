# Bitácora — Motor de eventos secuenciales v1

**Fecha:** 2026-08-18 17:35 UTC-5

## Entrega
- `engine/sequential_events.py` — cadena LIQ→SWEEP→DISP→STRUCT→OB→FVG→RETEST
- tests 4/4 PASS
- contrato + JSON H1 20Y

## H1 20Y (primera corrida)
- 1460 cadenas
- COMPLETE: 5 (2 bull / 3 bear)
- Mayoría expira en POOL (767) o POOL→SWEEP (575)
- Embudo deliberadamente estrecho (secuencia, no flags)

## Limitaciones v1
- STRUCTURE = BOS-lite
- EQH/EQL clusters causales simples
- No outcome/PnL aún

## Siguiente
Medir outcome solo sobre cadenas COMPLETE / profundidad ≥ N; integrar BOS/CHOCH tools canónicos.
