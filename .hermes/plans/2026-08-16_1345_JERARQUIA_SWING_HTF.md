# Plan: Jerarquía de Swings y Sesgo HTF según Tesis (7 fases)

**Fecha:** 2026-08-16
**Autor:** Hermes (bajo directiva de Ruben)
**Base de autoridad (NO invención):** `docs/ict/SPEC_TESIS_FORMAL.md` §42-49
(BIAS: entrada=D1/H4/H1 velas cerradas, salida=alineación D1→H4→H1, PRE sin
look-ahead, CRIT sesgo=último swing estructural MAYOR); `engine/bias/narrative.py`
T9 (sesgo=vigencia estructural SIN conteo fijo de velas, D1 autoridad raíz vía
`_compose_htf_bias`); `docs/ict/02_MSS_CHOCH.md` §79 (swing: ventana NO centrada
+ shift(lookback), sin look-ahead); `docs/motor_profesional_estado.md` §8.

**Hallazgo previo (evidencia):** 614.841 swings TODOS M5, lookback=5 hardcodeado
(≈1.8 swings/vela = ruido de microestructura). H4/D1 = 0 eventos. Esto viola
SPEC §47 (sesgo debe venir de swing MAYOR) y explica el 80% noise CHOCH /
96.5% noise BOS.

**Regla de ejecución:** al aprobar este plan, Hermes completa las 7 fases SIN
preguntar nada más. Solo se detiene ante bloqueo irrecuperable.

---

## FASE 1 — Lookback adaptativo por TF en `tools/swing.py`
**Autoridad:** SPEC §49 (umbral de "estructura mayor" = decisión de ing) +
§79 (ventana NO centrada + shift). El lookback es parámetro de ingeniería.
**Cambio:** `SwingTool` acepta `lookback` por TF vía tabla `TF_LOOKBACK =
{M5:5, M15:8, H1:12, H4:20, D1:30}`. Default por `tf` del frame. Sin romper
API actual (mantiene `lookback=5` como default M5). No crea archivo nuevo.

## FASE 2 — Cablear `swing_state` a los swings (metadato de vida del nivel)
**Autoridad:** regla memoria Ruben ("fresh/tested/mitigated/invalidated") +
`tools/swing_state.py` ya existe pero NO está cableado (grep confirmó).
**Cambio:** `SwingTool.run` marca cada swing con estado inicial `fresh`; se
actualiza a `tested`/`mitigated`/`invalidated` cuando un BOS/CHOCH opuesto lo
toca (reusa geometría de `bos_validate`). Esto es el "equivalente a human_score"
para swings: trazabilidad de vida del nivel, NO juicio de calidad (sigue N/A).

## FASE 3 — Generar datasets H4/D1 de swing (raíz de la tesis)
**Autoridad:** SPEC §42 (entrada bias = D1/H4/H1 velas cerradas).
**Cambio:** `scripts/gen_choch_dataset.py` y `gen_bos_dataset.py` ya leen H4/D1;
se añade extracción de swings H4/D1 y se escribe `data/learning/swing/EURUSD_H4_*.jsonl`
+ `D1_*.jsonl`. Esto llena el vacío de 0 eventos H4/D1. No crea archivo nuevo
(solo extiende los gen existentes).

## FASE 4 — Pipeline cascade bottom-up (maduración por acumulación)
**Autoridad:** tu propuesta + SPEC §44 (PRE: velas TF mayor COMPLETAMENTE
cerradas, sin look-ahead) + narrative.py T9 (vigencia, no conteo fijo).
**Cambio:** `engine/bias_from_tools.py` deja de usar `SwingTool(lookback=5)`
ciego sobre M5. Nuevo: lee M5→M15→H1→H4→D1 por timers de madurez (cada TF
solo recalcula con velas cerradas de ese TF), y reduce por `_compose_htf_bias`
(D1 autoridad raíz). Respeta `htf_frames` ya existente. Sin look-ahead.

## FASE 5 — Bias jerárquico alimenta rúbrica/encoder (ciere de loop)
**Autoridad:** SPEC §43 (salida = alineación D1→H4→H1).
**Cambio:** el `htf_ctx` de `teacher_rubric` (CHOCH/BOS) se llena desde el bias
jerárquico real (Fase 4), no `neutral`. El nature_head P5 puede usar `htf_ctx`
como feature. Esto hace que CHOCH/BOS se evalúen CONTRA la estructura mayor,
no aislados en M5.

## FASE 6 — Reetiquetar BOS/CHOCH con la nueva jerarquía
**Autoridad:** coherencia con §8 (rúbrica) + cierre de ciclo de auditoría.
**Cambio:** regenerar `features.jsonl` de CHOCH/BOS usando swings H4/D1 (Fase 3)
+ bias jerárquico (Fase 4), re-correr `label_human.py`. Reportar nueva
distribución human_score (debe subir % useful al alinearse con estructura mayor).

## FASE 7 — Bitácora + cuadro actualizados + commit/push (regla de oro)
**Cambio:** actualizar `.hermes-worklog/2026-08-16_1330_APRENDIZAJE_ICT.md` y
`docs/motor_profesional_estado.md` §8 con: lookback adaptativo, swing_state
cableado, conteo H4/D1, pipeline cascade, nueva distribución. Commit + push.
Verificar con `git ls-tree`/`git log` (regla de oro, sin afirmar).

---

## Orden de dependencias
F1 (lookback) → F2 (swing_state) → F3 (H4/D1) → F4 (cascade) → F5 (bias→rubrica)
→ F6 (reetiquetar) → F7 (doc+push).

## Qué NO se hace (límites de la tesis)
- NO se "califica" swing con human_score (sigue N/A primitivo; la tesis lo trata
  como pieza primaria, no setup).
- NO se usa ATR ni medias móviles (narrative.py:25, SPEC: geometría pura).
- NO look-ahead en ningún TF (SPEC §44, §79).
- NO se crean archivos nuevos salvo que la modularidad lo exija (F4 puede
  requerir un helper mínimo en engine/bias_from_tools.py; se decide al ejecutar).
