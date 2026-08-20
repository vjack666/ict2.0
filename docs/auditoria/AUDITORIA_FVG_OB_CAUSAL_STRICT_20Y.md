# Auditoría — Relación FVG/OB con orden causal estricto (20Y)

**Fecha:** 2026-08-18  
**Cambio:** `engine/relations.py` — `causal_mode="strict"` (default)  
**Data:** Dukascopy EURUSD 2006–2025

## Regla strict

```
same_direction + price_overlap
+ OB.candidate_bar < FVG.confirmation_bar
+ OB.confirmation_bar <= FVG.confirmation_bar
+ lag = FVG.confirm - OB.candidate <= max_bars_apart (20)
+ CausalLink parent=OB, child=FVG
```

Relación emitida: `FVG_OB_CAUSAL` (no `FVG_OB_OVERLAP`).

## Resultados 20Y

| TF | FVG | OB | Symmetric (legado) | **Strict** | OB-after-FVG eliminados | vs FVG | vs OB |
|----|----:|---:|-------------------:|-----------:|------------------------:|-------:|------:|
| H1 | 22477 | 2799 | 2318 | **702** | 1571 | 3.12 % | 25.1 % |
| H4 | 6497 | 862 | 716 | **206** | 497 | 3.17 % | 23.9 % |
| D1 | 1543 | 214 | 178 | **58** | 115 | 3.76 % | 27.1 % |

~70 % de los pares simétricos tenían el OB **después** del FVG → coincidencia geométrica, no origen del impulso.

## Tests

5/5 PASS (`tests/test_fvg_ob_relations.py`), incluido rechazo explícito de OB posterior al FVG.

## Veredicto

PASS técnico. La relación deja de ser simétrica y se alinea con la narrativa ICT “OB → impulso → FVG”. Sigue sin ser setup/entrada.
