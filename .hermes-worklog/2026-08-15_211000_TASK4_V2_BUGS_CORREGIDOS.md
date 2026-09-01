# Bitácora — Task 4 v2: CHOCH corrección de bugs (auditoría externa)

**Fecha:** 2026-08-15 21:10 UTC-5
**Tras auditoría del commit ea4ca4d, se encontraron 3 bugs de implementación.**

---

## Bugs corregidos (orden del auditor)
1. **Fallback muerto**: `if last_bos is None: continue` mataba el fallback de
   swings. Cambiado a `pass` (el bloque inferior infiere marea por swings).
2. **Mapeo de dirección roto en bos_filter.py** (2 sitios): `1 if BOS_UP else -1`
   convertia CHOCH_UP->-1. Cambiado a `"UP" in signal` / `"DOWN"/"DN" in signal`.
   Por eso unique_up siempre era 0.
3. **detail crasheaba**: `last_bos.id` protegido con `if last_bos is not None`.

## Números REPRODUCIBLES (EURUSD, confirm_bars=2, max_idle=0, HTF obligatorio)
### 1 mes recortado
```
TF     CHOCH_total  valid  unicos  up   dn
M5       2193        57     57     26   31
M15       730        26     26      9   17
H1        108         3      3      1    2
```
### Histórico amplio (A6: >=3-4 años)
```
TF     velas  CHOCH_total  valid  unicos  up  dn
H4      1500     518         19     19     9   10
D1       800     252         15     15     5   10
```
Ahora unique_up/unique_down salen correctos. D1 con 1 mes (24 velas) sigue 0
(esperado, A6), pero con historico amplio da 252 CHOCH (15 unicos). El fallback
funciona: ya no depende de tener BOS previo.

## Conclusión
Task 4 ahora SI esta bien cerrada: CHOCH en todas las TFs, direccion correcta,
fallback operativo, numeros reproducibles. Sesgo: M5 mezcla up/dn (26/31), ya no
el 100% DOWN erroneo del bug de mapeo.

## Siguiente
Task 5: tools/fvg.py. Luego Fase 2 (aprendizaje humano).
