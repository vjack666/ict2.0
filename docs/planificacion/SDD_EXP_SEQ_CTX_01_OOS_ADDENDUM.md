# Addendum — Ampliación OOS pre-registrada (EXP-SEQ-CTX-01)

**Fecha pre-registro:** 2026-08-23
**Autor:** Hermes (Dirección de Laboratorio)
**Estado:** PRE-REGISTRADO (antes de ejecutar; no se ajustan criterios post-resultado)
**Padre:** `docs/planificacion/SDD_EXP_SEQ_CTX_01_OOS_DATASET.md` (Ítem 2)

---

## 1. Motivación (hecho verificado)

El holdout actual (2021–2025) de la variante `lite` tiene:
- `ALIGNED=7`, `AGAINST=7`, `NEUTRAL=1` → **subpotenciado** (<30 por bucket).
- Signo negativo en ambos (`mean_end_24` ALIGNED=-0.0015, AGAINST=-0.0044).

No se puede declarar estabilidad OOS. Se requiere ampliar la observación SIN
ajustar criterios tras ver resultados.

## 2. Bloques temporales (CONGELADOS, no se mueven)

| Bloque | Rango | Regla |
|---|---|---|
| DESIGN | 2006–2015 | train interno |
| VALIDATION | 2016–2020 | selección de especificación (no de thresholds) |
| HOLDOUT | 2021–2025 | evaluación final, intocable |

`+48` debe permanecer dentro del bloque; lo que cruza el límite se excluye
(reporte de exclusiones), no se reclasifica.

## 3. Especificación de la ampliación (pre-registrada)

| Parámetro | Valor pre-registrado |
|---|---|
| Población | EURUSD H1 20Y (124.377 barras) completo |
| Unidad de muestra | nodo k de `SequentialChain` (event-anchored), dedup por `(chain_id, k)` |
| Variante estructural | `lite` (ablación) Y `canonical_bos` (primaria), en datasets SEPARADOS |
| Deduplicación | por `(structure_bar, direction)` dentro de cada variante |
| Horizontes | `label_end_6 / 12 / 24 / 48` (fijos, no se elige el mejor) |
| Splits | temporales DESIGN/VAL/HOLDOUT (no aleatorio) |
| Criterio mínimo de suficiencia | `n >= 30` por celda `(variante × context_bucket × bloque)` |
| Tratamiento de resultados negativos | se conservan y se reportan; no se descartan buckets desfavorables |
| Diferencia entre bloques | se registra siempre (DESIGN vs VAL vs HOLDOUT) |

## 4. Reglas anti-p-hacking (obligatorias)

- No ampliar SOLO porque un resultado parezca favorable.
- No ajustar thresholds usando el holdout.
- No cambiar horizontes, contexto ni deduplicación tras ver resultados.
- Si HOLDOUT sigue <30/bucket → declarar SUBPOTENCIADO y dejar dataset en
  `WAITING_FOR_OOS_EVIDENCE`.
- Conservar SIEMPRE resultados negativos y diferencias entre bloques.
- No mezclar OOS de `lite` con el de `canonical_bos`.

## 5. Criterio de cierre de la ampliación

La ampliación se considera concluida cuando:
- se reporta n por celda en los 3 bloques,
- y se declara explícitamente `SUFICIENTE` (n>=30 en holdout) o
  `SUBPOTENCIADO` (holdout <30),
- sin haber tocado criterios post-resultado.

Este addendum es la evidencia de pre-registro. La ejecución (Trabajo 4, fábrica
de dataset) consumirá esta especificación.
