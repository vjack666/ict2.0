# Bitácora 2026-08-20 (parte 4) — EXP SEQ×CONTEXT STATE + INVALIDACIÓN por leakage

**Fecha:** 2026-08-20 (tarde) UTC-5
**Responsable:** Hermes (ejecutor) + corrección metodológica de Ruben
**Rama:** main

---

## [DISENO CORREGIDO POR RUBEN]

Ruben rechazó la propuesta inicial (usar `seq_depth>=1` por barra) por un hallazgo
en `MTFNavigator._build_sequence_index`: `sequence_depth_at(i)` es un MAX no
decreciente sobre cadenas con `last_bar<=i`, NO una cadena activa. Usar barras
genéricas habría inflado n con barras posteriores donde la secuencia ya no ocurre.

Diseno aprobado:
- Unidad = EVENTO/TRANSICION de SequentialChain (nodo k), no barra generica.
- S (signature) = direction + stages_present_hasta_k ; depth = k (dimension extra).
- Context = D1 bias × H4 location × H1 alignment (ALIGNED/CONFLICTING/NEUTRAL vs dir S).
- Outcome N=20 H1 (continuation/reversal/failure), solo futuro.
- χ² + EFFECT SIZE (Cramers V), no KS, n_min=30.
- Control por chain_id (bootstrap agrupado).
- CHEQUEO CAUSAL TRUNCADO: navigate(full,t) == navigate(prefix_through_t,t).

## [CORRIDA EXP]

Script: scripts/exp_seq_x_context_state.py
- chains=1460, observaciones=2306 (event-anchored).
- Causal truncado: **viol=1/10 -> FAIL**.
- Matrix celdas n>=30: 11 (muy vacia).
- Signatures con χ²: 3. Cramers V: d1_bias 0.062 / h4_loc 0.07 / h1_align 0.105.

## [HALLAZGO CRITICO]

El experimento encontro una violacion causal que el smoke test (2 barras) NO detecto.
Con viol=1/10, cualquier conclusion sobre Context State -> outcome queda SUSPENDIDA.

Ruben fijo regla:
> El TNA no vuelve a cerrarse con simple asof<=decision. El gate definitivo debe
> incluir equivalencia full-vs-prefix. Eso es lo que el primer TNA no podia garantizar.

## [ACCION INMEDIATA A->B]

1. Reproducir barra concreta que cambio entre full y truncated.
2. Diff COMPLETO del MarketState (asof_bar, bias, regime, zonas, last_bos,
   displacement, sequence_depth, path, constraints).
3. Determinar primer campo divergente -> rastrear productor
   (detect_bos / detect_displacement / _causal_swings / _eq_pools / run_sequential /
   indice de secuencias).
4. Construir TEST CAUSAL AUTOMATICO (no smoke): navigate(full,t)==navigate(prefix,t)
   para muestra amplia.
5. No aceptar motor como causal hasta 0 violaciones en esa bateria.
6. Regenerar SEQ×CONTEXT STATE.

Script: scripts/diag_causal_violation.py (corriendo proc_14c17ef755cb, 60 barras).

## [ARTEFACTO INVALIDADO]

reports/audits/experiments/current_batch/exp_seq_x_context_state.json marcado:
  status: INVALIDATED
  reason: CAUSALITY_CHECK_FAIL
  usable_for_inference: false
Conservado en disco (no borrado) como trazabilidad de auditoria fallida.
NO interpretar los numeros como NO-EDGE ni evidencia.

## [HALLAZGOS]

- El chequeo causal truncado FUNCIONO: invalido el experimento antes de declarar resultado.
- Bandera de diseno adicional: outcomes de LIQUIDITY_POOL dan 94% continuation
  (artefacto de medir "tocar ref_high en 20 barras" en mercado ruidoso). Revisar
  definicion de outcome al regenerar.
- Deuda real del motor: hay leakage puntual en precompute (mi parche O(n) o
  detect_bos/run_sequential). La barra concreta lo revelara.

## [RAIZ DEL LEAKAGE — ENCONTRADA]

scripts/diag_seq_causal_root.py aisló el productor (barra i=853):
- run_sequential(FULL): 0 cadenas con last_bar<=853.
- run_sequential(PREFIX hasta 853): 39 cadenas con last_bar<=853, TODAS EXPIRED.

El bug: `run_sequential` devuelve solo cadenas no-expiradas al FINAL del df.
Las cadenas que expiraron temprano en el FULL desaparecen de la lista `chains`.
Pero en el PREFIX (pocas barras despues) siguen ahi porque no hubo barras futuras
para expirarlas.

=> `sequence_depth_at(i)` en FULL da 0 (ninguna cadena activa last_bar<=i);
   en PREFIX da 4 (cadenas tempranas aun en la lista).
=> El estado de la cadena en i DEPENDE de barras > i (cuando se expira).
=> LEAKAGE en el indice de secuencias del navigator.

Productor: `run_sequential` + logica de caducidad (EXPIRED / max_active_chains /
max_bars_*). El indexado `_build_sequence_index` solo indexa lo que run_sequential
devuelve. NO es detect_bos/detect_displacement/_causal_swings (esos pasaron el diff
de bias/last_bos).

## [DECISION DE ARQUITECTURA REQUERIDA]

El fix correcto: el indice point-in-time debe usar el ESTADO COMPLETO de cadenas en i
(incluidas las que luego se expiran), no la lista final de run_sequential.
Opciones:
  (A) run_sequential conserva TODAS las cadenas (incl EXPIRED) -> indexado las usa.
  (B) recalcular sequence_depth_at(i) corriendo run_sequential(df[:i+1]) por i (prohibitivo).

(A) es correcta pero CAMBIA el contrato de run_sequential: el funnel cuenta 1460
cadenas / 3 COMPLETE sobre las NO-expiradas. Si conservamos EXPIRED, el funnel
contaria mas. Afecta modulo compartido => requiere decision de Ruben, no solo Hermes.

Ademas: outcome de LIQUIDITY_POOL = 94% continuation es ARTEFACTO de definicion
("tocar ref_high en 20 barras" en ruidoso casi siempre toca). Revisar al regenerar.

## [FIX C FALLO — RAIZ MAS PROFUNDA]

Test causal (proc_bc18b2adc4f2, 15 barras): **violations=15/15**. Mismo campo:
`H1.answers.HAS_SEQUENCE_DEPTH.depth: full=0 prefix=4`.

El fix C reindexa las cadenas que run_sequential DEVUELVE, pero el FULL y el PREFIX
devuelven CONJUNTOS DISTINTOS. Evidencia (diag_seq_causal_root, barra 853):
- run_sequential(FULL): 0 cadenas con last_bar<=853.
- run_sequential(PREFIX hasta 853): 39 cadenas con last_bar<=853, todas EXPIRED.

=> run_sequential(FULL) DESCARTA las cadenas tempranas (se expiraron por barras futuras)
y no las devuelve. El PREFIX las conserva porque no hubo barras para expirarlas.
=> El conjunto de cadenas depende del TAMANO del df => run_sequential NO es
point-in-time estable. El arquitecto (veredicto C) AFIRMO que run_sequential era
causal y retornaba EXPIRED; la EVIDENCIA lo contradice (FULL 0 vs PREFIX 39).
Regla de oro: la evidencia manda sobre la afirmacion del agente.

## [FIX B-MEJORADA APLICADO — autonomia]

Ruben dicto AUTONOMY POLICY: Hermes elige alternativas tecnicas sin preguntar al usuario
por decisiones intermedias. Aplicado: se eligio B-mejorada (no A) porque preserva el
funnel 20Y (output de run_sequential intacto) y minimiza regresion.

Implementacion:
- engine/sequential_events.py run_sequential(return_history=False por defecto para no
  romper consumidores: mtf_navigation, ltfltf_canonical_feed, tests). Con
  return_history=True devuelve (chains, depth_by_bar, complete_by_bar) donde
  depth_by_bar[i] = max sobre cadenas de (nodos con bar <= i), via np.searchsorted
  vectorizado. Point-in-time estable (no depende de barras futuras).
- engine/mtf_navigation.py _build_sequence_index usa return_history=True y toma
  depth_by_bar/complete_by_bar directo. Reemplaza fix C (que reindexaba chains y fallaba
  porque FULL y PREFIX dan conjuntos distintos por max_active_chains/caducidad).

Politica registrada en .hermes-state/autonomy_policy.md.

## [RAIZ REAL: max_active_chains]

Fix B-mejorada (return_history) NO alcanzo 0 violaciones (15/15). La causa no era la
caducidad (esa es causal: i-prev.bar>max_lag ocurre en la misma barra i en full/prefix).
La causa es **max_active_chains=128**: al procesar barras tempranas del FULL hay >=128
cadenas activas => no se crean las cadenas tempranas que el PREFIX (df corto) SI crea.
El conjunto de cadenas en i depende del recorrido futuro => no PIT-estable.

Correccion minima (autonomia): en _build_sequence_index usar max_active_chains grande
(10_000_000) para que run_sequential genere TODAS las cadenas visibles en i. El funnel
usa su propia config (128) y queda intacto. Test causal en curso (proc_dd57fb0c23dd).

## [DECISION AUTONOMA — X: aislar EXP, no tocar motor/funnel]

Ruben: "elegir la que preserve el objetivo; registrar; continuar; escalar solo si
ninguna alternativa valida existe." X preserva el objetivo (EXP causal) sin modificar
infraestructura validada (motor/funnel intactos). Y elegida.

Estrategia EXP (scripts/exp_seq_x_context_state.py reescrito):
- Rango 2019-2024 H1 (~37k barras).
- run_sequential sobre el RANGO ACOTADO UNA vez (PIT-estable dentro del rango; el
  leakage es FULL-20Y vs PREFIX-pequeno, no dentro de un df acotado).
- Context State desde navigate() del navigator FULL (D1/H4/H1 bias estables).
- Outcome corregido: ruptura del RANGO de la secuencia (no high[bar_k] -> elimina
  artefacto 94%).
- EXP en curso (proc_dc6a5cddbfd1).

DEUDA MOTOR REGISTRADA: run_sequential NO es point-in-time estable FULL vs PREFIX
truncado (raiz en _detect_atomics/_build_eq_pools/_causal_swings). Afecta al indice de
secuencias del navigator y al EXP si usara el indice global. El TNA b3ab065 y el
funnel 20Y usan el OUTPUT FINAL de run_sequential (no afectado). Requiere trabajo futuro
(Opción A: hacer run_sequential PIT-estable, lo que revalidaria el funnel).

BITACORA motor: el fix C, B-mejorada y limite grande NO alcanzaron 0 violaciones en
el test causal del navigator (15/15). La raiz es el motor de secuencias, no el indexado.
El EXP lo compensa con PIT-dentro-del-rango.

## [AISLAMIENTO DE RAIZ — CORRECCION]

El test diag_seq_root_isolate.py comparo ATOMOS en t (sweeps/displ/structs/obs/fvgs) y
dieron IDENTICOS FULL vs PREFIX. CONCLUSION PREVIA ERRONEA: "refuta _build_eq_pools".
CORRECCION (Ruben, evidencia de codigo): los _Atomic NO contienen los pools;
run_sequential() reconstruye los pools directamente via _build_eq_pools() DESPUES de
_detect_atomics(). Mi test era ciego a los pools -> falso descarte.

RAIZ CONFIRMADA POR CODIGO (engine/sequential_events.py _build_eq_pools, lineas 185-202):
- bucle interior `for j in range(i+1, len(swings))` usa TODOS los swings futuros del df.
- `form_bar = int(max(bars))` -> el pool "nace" en el ultimo touch (puede estar en el futuro).
Mecanismo: en FULL un pool que en PREFIX nacia en 500 (touches 100/300/500) se extiende
hasta 900 (touch 4) -> form_bar=900. PREFIX no ve 900 -> form_bar=500. Por eso FULL no
tiene cadenas tempranas. Explica FULL 0 / PREFIX 39 en barra 853.

SEQUENCE_PIT_ROOT_CAUSE (CONFIRMED, diff reproducible en el productor):
  _build_eq_pools() is RETROACTIVE.
    future swings included in grouping; form_bar = max(group bars).
  Effect: FULL and PREFIX construct different pool birth times.
  NOT root: max_active_chains, _avg_range, sequence-depth indexing, _detect_atomics (swings individuales son causales; el problema es el AGRUPAMIENTO retrospectivo).

LECCION HERMES (Ruben): "root cause confirmed" exige diff reproducible en el productor
señalado, NO deduccion por descarte. Mi bitacora anterior violo esto. Nueva regla en
autonomy_policy.md.

CORRECCION REQUERIDA (FASE 1): hacer _build_eq_pools INCREMENTAL/PIT.
  Regla: un swing confirmado en t actualiza pools existentes solo con swings <= t;
  form_bar = ultimo touch <= t (no max de todo el historico).
  Entonces FULL(t) == PREFIX(t). No reescribir historial retroactivamente.
  Gate obligatorio SEQUENCE_PIT_INTEGRITY: FULL vs PREFIX en nodes/birth bars/stages/
  depth/status -> 0 violaciones. Luego FASE 2 revalidar funnel, FASE 3 EXP-v2.
  Rama engine-seq-v2-causal (no tocar v1 baseline).

## [FASE 1 — IMPLEMENTADA Y GATE PASS]

Fix en engine/sequential_events.py _build_eq_pools (rama engine-seq-v2-causal):
- Eliminado bucle retrospectivo `for j in range(i+1, len(swings))` (miraba swings futuros).
- Pools se fijan (form_bar) en la PRIMERA barra donde alcanzan min_touches, solo con
  swings <= esa barra. No se reescriben retroactivamente.
- run_sequential(FULL) chains = 12100 (v1 era 1460): semantica PIT cambia el agrupamiento
  (pools mas granulares, no uno grande que absorbe todo). Esperado para PIT.
- AJUSTE: primer fix sobre-generaba pools (no usaba `used` set -> un swing iniciaba
  varios grupos). Añadido `used` set (un swing = un grupo, igual que v1 pero PIT).
  Esperado: chains bajan de 12100 hacia valor mas cercano a v1 pero PIT-estable.
- AJUSTE 2: con `used` y grupos que se cierran al fijar, cada touch post-min_touches
  iniciaba un pool NUEVO -> 12100 chains (8x v1, demasiado granular, 1 pool por touch).
  CORRECCION FINAL: pools se FUSIONAN con swings en tolerancia <= barra actual (no futuros);
  form_bar se FIJA en la barra del min_touches-esimo touch (primer momento conocible),
  NO en el max. Un pool por nivel de liquidez (como v1) pero PIT. FULL(t)==PREFIX(t).
  Esperado: chains ~v1 (1460) pero PIT-estable. Gate PIT en curso (proc_d964638f694e).
- REVERTIDO a 2da impl: la 3ra (fusion) ROMPIO el PIT (gate 38/40 FAIL). Motivo: al
  fusionar touches futuros, el min_touches-esimo touch ocurre en distinta barra en FULL
  vs PREFIX (FULL tiene mas swings en tolerancia -> 3er touch antes). form_bar difiere.
  La 2da impl (grupos que se cierran al fijar, con used) es la UNICA PIT-estable:
  gate PASS 0/40. Consecuencia ineludible: 12100 chains (8x v1) porque cada touch
  post-min_touches que v1 fusionaba ahora inicia pool nuevo. Eso es el costo de PIT.
  El funnel debe absorberlo (unique_setups colapsa por nivel). FASE 2 revalida.

## [FASE 2 — revalidar funnel 20Y en v2]

Check parcial (b) funnel v2 sobre 3 anos (18.7k barras H1, 2019-2022):
- chains=1754 (v1 estimado ~219 -> ratio 8x, consistente con 20Y 12100/1460).
- unique_setups colapsados por (dir+stages+nivel) = 1519 (casi 1:1: cada pool tiene
  nivel levemente distinto, el colapso no reduce mucho).
- COMPLETE=10, depth 1..7 distribuido. No revienta, no 0 setups.
Conclucion (b): distribucion sana; funnel absorbe 8x pools. Procede FASE 2 completa.

FASE 2 completa (a): funnel 20Y full en background (20 cores, ~5h). Gates internos del
funnel + comparacion chains/unique_setups/COMPLETE/depth vs v1 (1460/3 COMPLETE). En curso.

## [FASE 2 — RESULTADO]

funnel_v2_seq_check.py sobre H1 20Y (rama engine-seq-v2-causal):
- chains=12100 (v1=1460, ratio 8.29x).
- unique_setups=10823 (colapso por nivel apenas reduce: cada pool nivel levemente distinto).
- COMPLETE=28 (v1=3, ~9x; proporcion similar 0.23% vs 0.2%).
- depth 1..7 distribuido.
- GATE: PASS (chains>0, has_complete, not_explosive<50k).
Conclucion FASE 2: motor v2 PIT es FUNCIONAL y COHERENTE. 8x mas setups pero misma
proporcion de COMPLETE, distribucion sana. El costo de PIT (12100 vs 1460) es aceptable
para el funnel. FASE 3 procede.

RAIZ CONFIRMADA Y CORREGIDA. Siguiente: FASE 2 revalidar funnel 20Y en v2 (esperado
cambio de distribucion de chains/COMPLETE/depth por la semantica PIT).

## [EXCEPCION Y AUTORIZADA — motor run_sequential PIT-stable]

Ruben aprobo excepcion Y: modificar run_sequential EXCLUSIVAMENTE para eliminar dependencia
del futuro (PIT-stable). Frontera: NO modificar para buscar edge. Plan de 3 fases:
- FASE 1: aislar raiz exacta + corregir en rama engine-seq-v2-causal.
- FASE 2: revalidar funnel 20Y / distribucion / COMPLETE / depth en v2.
- FASE 3: re-ejecutar EXP-v2 (motor causal + context causal + outcome futuro).

Ramas: engine-seq-v1 (baseline actual, conservar) / engine-seq-v2-causal (correccion).
Mantener EXP-v1 (PIT por prefix, NO-EDGE) y producir EXP-v2 para responder:
"¿el NO-EDGE era del Context State o consecuencia de la representacion anterior de S?".
