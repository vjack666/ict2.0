# Bitácora — Task 5b: adaptador bias del motor usando tools corregidos

**Fecha:** 2026-08-15 21:40 UTC-5
**Decisión del Director:** "si hacemos una mejora al motor, lo más lógico es que
esa mejora sea para el uso real." -> las mejoras de Fase 1 (Swing/BOS/CHOCH
corregidos) deben alimentar el sesgo del motor, no quedar aisladas en tools/.

---

## Qué se construyó
engine/bias_from_tools.py — adaptador que produce un df anotado compatible con
engine.plan (_bias_from_frame) pero USANDO las herramientas corregidas de tools/:
- SwingTool (objeto persistente)
- BOSTool + apply_validation (ACTIVE/INVALIDATED)
- filter_bos_thesis (confirm_bars=2, fusion, HTF) -> bos_real
- CHOCHTool (fallback de swings) + filtro tesis

Columnas emitidas: bos_dir, bos_status, bos_real, bos_level, choch_dir,
choch_status, choch_proj_level. Compatibles con engine.plan.

bias_from_tools(df, t) replica la semantica de _bias_from_frame (CHOCH activo
manda sobre BOS activo) E INCLUYE la regla T9.7 del motor viejo (CHOCH solo
cuenta si el BOS contrario era REAL, bos_real). Asi la mejora de calidad
(filtro tesis -> bos_real) se propaga al sesgo.

## Evidencia (EURUSD M5 1 mes, 2026-07-14..08-14)
- annotate_with_tools(M5): 84 BOS active, 2193 CHOCH active, 5 bos_real.
- bias_from_tools(M5) = BULLISH.
- annotate_with_tools(D1 hist amplio): bias = BEARISH.

## Hallazgo honesto (discrepancia con motor viejo)
_bias_from_frame (motor viejo) sobre el MISMO df anotado por tools da BEARISH,
mientras bias_from_tools da BULLISH. Causa: el motor viejo fue disenado para SU
propia anotacion (detect_market_structure); al correrlo sobre un df hibrido
anotado por tools, su check T9.7 (busca bos_level atras por choch_proj_level
con tol) diverge porque tools y engine etiquetan eventos distinto. NO es un bug
del adaptador: es una mezcla hibrida no prevista.

DECISION: el motor de lectura real debe usar bias_from_tools (fuente de verdad
cuando use_tools=True), no _bias_from_frame sobre df hibrido. bias_from_tools es
autonomo y coherente. engine/plan.py NO se modifico (respeto regla de no mezclar
legado); quien orqueste puede importar bias_from_tools directo.

## Aislamiento respetado
engine/ importa tools/ (permitido: orquestador consume tools). tools/ NO importa
engine/ (invariante Task 2).

## Siguiente
Fase 4: orquestador que llame bias_from_tools en cascada TF (D1->H4->H1->M15->M5)
para el bias de lectura real del motor.
