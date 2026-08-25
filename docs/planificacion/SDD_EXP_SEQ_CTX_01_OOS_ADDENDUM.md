# Addendum — Ampliación OOS pre-registrada (EXP-SEQ-CTX-01)

**Fecha pre-registro:** 2026-08-23
**Autor:** Hermes (Dirección de Laboratorio)
**Estado:** PRE-REGISTRADO (antes de ejecutar; no se ajustan criterios post-resultado)
**Padre:** `docs/planificacion/SDD_EXP_SEQ_CTX_01_OOS_DATASET.md` (Ítem 2)

---

## 1. Motivación histórica (hecho verificado)

La línea base V1, antes de corregir la semántica de `context_bucket`, reportaba
para el holdout 2021–2025 de la variante `lite`:
- `ALIGNED=7`, `AGAINST=7`, `NEUTRAL=1` → **subpotenciado** (<30 por bucket).
- Signo negativo en ambos (`mean_end_24` ALIGNED=-0.0015, AGAINST=-0.0044).

Ese conteo ya no es el estado vigente del artefacto. Se conserva como referencia
histórica; no se usa para cerrar el Gate OOS. La regeneración corregida se
describe en §7 y mantiene el mismo criterio sin ajustarlo tras el resultado.

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

---

## 6. Resultado de ejecución V2 previo a la corrección semántica

Este bloque conserva el resultado histórico de la fábrica anterior. No es la
fuente vigente para los conteos OOS.

La fábrica local aplicó literalmente la unidad `SequentialChain node k` y la
deduplicación `(structure_bar, direction)` por variante. Se excluyeron 12 filas
duplicadas de `canonical_bos`, 48 de `lite` y 4 filas de `lite` cuyo `T+48`
cruzaba el límite del bloque. No se movieron observaciones entre splits.

| Dataset | Total | DESIGN | VALIDATION | HOLDOUT |
|---|---:|---:|---:|---:|
| `canonical_bos` | 100 | 36 | 44 | 20 |
| `lite` | 192 | 84 | 52 | 56 |

Conteo HOLDOUT por bucket:

- `canonical_bos`: ALIGNED=20, NEUTRAL=0, AGAINST=0.
- `lite`: ALIGNED=36, NEUTRAL=3, AGAINST=17.

**Veredicto histórico:** `SUBPOWERED`; el criterio pre-registrado
`n >= 30` por `(variante × context_bucket × HOLDOUT)` no se cumple. El estado
del manifest permanece `WAITING_FOR_OOS_EVIDENCE`. Este resultado es descriptivo
y no autoriza inferencia, backtest, entrenamiento ni operación.

---

## 7. Regeneración corregida V3 (2026-08-24, estado vigente)

La fábrica ahora calcula el bucket desde `sequence_direction`, `d1_bias`,
`h4_location` y `h1_alignment`, y conserva esos inputs en cada fila. El total
de eventos no cambió: 292 filas, con las mismas exclusiones de deduplicación y
purga `+48`.

| Dataset | DESIGN | VALIDATION | HOLDOUT |
|---|---:|---:|---:|
| `canonical_bos` | 36 | 44 | 20 |
| `lite` | 84 | 52 | 56 |

HOLDOUT por bucket:

- `canonical_bos`: ALIGNED=6, NEUTRAL=11, AGAINST=3.
- `lite`: ALIGNED=10, NEUTRAL=36, AGAINST=10.

**Gate OOS vigente:** `SUBPOWERED`; ninguna variante cumple `n>=30` en todas
las celdas. El estado sigue `WAITING_FOR_OOS_EVIDENCE`. La corrección reparó
la clasificación, pero no creó eventos adicionales.

Los snapshots y checkpoints skeleton creados posteriormente se consideran
artefactos de infraestructura no operativos: no contienen pesos aprendidos, no
declaran edge y no cambian este veredicto OOS.

---

## 8. Reconciliación de ampliación multi-símbolo (2026-08-24)

**ACTUALIZACIÓN OBLIGATORIA:** este addendum (fecha pre-registro 2026-08-23) describe
la ampliación original como "EURUSD H1 20Y" con veredicto V3 `SUBPOWERED` (§3, §7). Con
posterioridad se ejecutó una **ampliación multi-símbolo pre-registrada** distinta
(`docs/planificacion/OOS_EXPANSION_PREREGISTRATION.md`) que REEMPLAZA el diseño de §3:
universo = 8 símbolos × {canonical_bos, lite} × HOLDOUT 2021–2025 (+ EURUSD
DESIGN/VALIDATION). El criterio `n>=30` y la regla anti-p-hacking se mantuvieron.

**Resultado de la ampliación multi-símbolo (HECHO VERIFICADO, evidencia en disco):**
- `canonical_bos`: ALIGNED=19, NEUTRAL=110, AGAINST=23
- `lite`: ALIGNED=24, NEUTRAL=177, AGAINST=44
- Total = 625 filas; HOLDOUT = 397 filas.
- Universo **agotado** (8 símbolos procesados).
- Veredicto estadístico: **`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`** (3/6
  celdas < 30 pese a agotar el universo).

**Autoridad:** los artefactos en `data/learning/seq_ctx_01/OOS_EXPANSION/` mandan sobre
este texto. El §3 de este addendum queda SUPERSEDED por el preregistro multi-símbolo
para todo lo relativo a la ampliación ejecutada; el resto (bloques temporales
congelados §2, reglas anti-p-hacking §4) sigue vigente.

**Estado canónico de EXP-SEQ-CTX-01:**
`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE` — 625 filas totales, 397 HOLDOUT,
canonical_bos 19/110/23, lite 24/177/44, 3/6 celdas < n>=30, sin snapshot, sin
entrenamiento, sin edge, `can_trade=false`.
