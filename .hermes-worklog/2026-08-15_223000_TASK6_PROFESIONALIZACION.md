# Bitácora — Task 6: profesionalización BOS/CHOCH (gate + score + displacement)

**Fecha:** 2026-08-15 22:30 UTC-5
**Plan:** `.hermes/plans/2026-08-15_220000_BOS_CHOCH_CALIDAD.md` (v1.1 aprobada)
**Directiva:** rescatar mejoras de SMC, adaptar a nuevo motor, uso diario definitivo.

---

## Qué se construyó (rescate aislado de SMC-SYSTEMS, SIN ATR, geometría pura)
- tools/displacement.py — rango promedio high-low (migrado de ATR en SMC). OK.
- tools/quality_score.py — score 0-1 + is_real (de _compute_bos_quality). OK.
- tools/choch_quality.py — EXP-012 CHOCH real (momentum+after-BOS+nivel). EN DEBATE.
- tools/swing_state.py — ObjectState fresh/tested/mitigated/invalidated. OK.
- engine/bias_from_tools.py — integra todo; motor usa bias_from_tools. OK.

## Evidencia (EURUSD M5 1 mes 2026-07-14..08-14)
- bias M5 = BULLISH (pipeline profesional).
- BOS active 84; quality_score en 1609; BOS REAL (score>=0.5) = 1258.
- displacement_bullish 109 velas, bearish 84 velas.
- CHOCH active 2193; CHOCH REAL (gate) = **1** (M5), 0 (H4), 0 (D1).

## HALLAZGO CRÍTICO (honesto, no oculto)
El gate CHOCH con DESPLAZAMIENTO como VETO da ~1 evento/mes en M5.
Causa raíz (debug barra 2447): el CHOCH rompe el nivel (after_bos=True,
momentum=True, pivot presente) pero la vela de ruptura NO tiene
desplazamiento (cuerpo >=1.5x rango, mecha<40%) ni en las 2 siguientes.
En M5 los CHOCH rompen por mecha/cuerpo pequeño; el desplazamiento es raro
en la vela exacta. Exigirlo mata el 99.9%.

El plan v1.1 puso "desplazamiento mínimo" en el gate (veto). En la práctica
es DEMASIADO estricto para CHOCH (el desplazamiento es propio del BOS de
continuación, no del aviso de giro). Resultado operativo: ~1 CHOCH/mes.

## DECISIÓN PENDIENTE (tradeoff, no bug menor)
- Opción A: desplazamiento SOLO como bonus de score (CHOCH REAL = nivel +
  after-BOS opuesto; disp suma puntos al score 0-100, no veta). Esperado:
  ~docenas de CHOCH reales/mes (útil).
- Opción B: mantener desplazamiento como veto (resultado: ~1/mes, muy
  limpio pero casi nada operable).

Se deja commiteado el estado (gate actual = veto) y se consulta al Director.

## Estado
- displacement/quality_score/swing_state/bias_from_tools: FUNCIONAN.
- gate CHOCH: necesita decisión de diseño (A vs B).
- NO se afirma "CHOCH profesional completo" hasta resolver A/B.
