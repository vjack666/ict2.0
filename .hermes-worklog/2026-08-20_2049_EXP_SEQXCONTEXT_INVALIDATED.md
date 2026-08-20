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

reports/audits/exp_seq_x_context_state.json marcado:
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
