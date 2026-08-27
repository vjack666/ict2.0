# FASE 4.2 — Validación integrada ICT + Wyckoff (Persistent Market State)

- **Fecha:** 2026-08-27
- **Agente:** Hermes
- **Disparador:** Dictamen CEO — FASE 4.1 causalmente bien, pero la aceptación se hizo SIN `--wyckoff`. Validar ICT+Wyckoff juntos sin edge ni IA.
- **Base:** worktree Codex `5623a7b` (FASE 4.1) + `scripts/verify_fase42_wyckoff_integration.py` (nuevo)

---

## 1. OBJETIVO

Responder la pregunta del CEO:

> ¿El visor corregido sigue siendo 100% causal cuando Market State, AHF e
> información Wyckoff funcionan SIMULTÁNEAMENTE?

No buscar rentabilidad. Runtime declarado: `RUNTIME_BASIC_NOT_WYCKOFF_7`.

## 2. CORRIDA

- `scripts/export_visual_backtest.py --symbol EURUSD --timeframe M15 --tfs D1 H4 H1 M15 M5 M1
  --start 2024-01-02 --end 2024-01-02 --warmup-bars 200 --wyckoff --wyckoff-authority-tf H1
  --wyckoff-layers D1 H4 H1 M15 --multitf-context --horizon-bars 200`
- `run_id=6cfda78f285625ee504ff0e6`
- Ventana: 96 velas M15 visibles, 1438 M1, 288 M5, 24 H1, 6 H4, 1 D1.
- `structure_events=120`, `wyckoff_events=83`, `trades=1` (diagnóstico, no señal).
- Seguridad artifact: `diagnostic_only:true, entry_authorized:false, can_trade:false,
  can_train:false, promotion_authorized:false`.

## 3. GATE FASE 4.2 — 9/9 PASS

```
market_state_present:    PASS
ahf_state_present:       PASS
wyckoff_snapshot_present: PASS
ict_wyckoff_coexist:     PASS
authority_tf_present:    PASS
six_tf:                  PASS   (D1/H4/H1/M15/M5/M1)
full_eq_prefix:          PASS   (pit_temporal_consistency PASS, 0 divergencias)
future_leakage_zero:     PASS
runtime_basic_not_wyckoff_7: PASS
OVERALL: PASS
```

## 4. HALLAZGO DE RENDIMIENTO (no bloqueo de correctitud)

`backtest/wyckoff_timeline.py:build_wyckoff_timeline` (L133-136) hace
`_closed_prefix(frames["M1"], decision_time).copy()` por cada vela visible del
`main_tf`. Con ventanas de 2-3 semanas y M1 (91MB / ~130k velas) esto es O(velas_M15
× velas_M1) en CPU y hace la corrida muy lenta (maté de 6-23 min en intentos de 2-3
sem). La corrida de 1 día (96 velas M15) terminó en <2 min y es suficiente para el
gate. **No es un memory leak** (RAM confirmada 24MB; mi lectura previa de "23GB" fue
error de etiqueta: tasklist da KB). Es optimización de rendimiento, fuera del
write-set FASE 4 sin tu autorización de push. Documentado como deuda técnica.

## 5. WYCKOFF-7 (multiagentes, diseño puro, posterior)

Por instrucción CEO ("cuando legues a WYCKOFF-7 avísame, envía multiagentes"),
despaché 3 subagentes en paralelo con write-set disjunto (solo documentación, sin
tocar engine/backtest). Completados en ~5 min:

- `docs/planificacion/DISENO_WYCKOFF_7_PERSISTENT_RANGE.md` — entidad persistente
  `WyckoffRange`, `range_id`, `episode_id`, fases A→E, eventos Spring/Test/SOS/LPS
  como transiciones de estado; compatible con `ObjectState`/`ObjectType`.
- `docs/planificacion/DISENO_CAUSALIDAD_WYCKOFF_RANGE_PIT.md` — corte PIT
  (`decision_time <= T`), `history` estilo `AHFTransition`, campo de verificación
  PIT para FULL==PREFIX.
- `docs/contratos/WYCKOFF7_SEMANTICA_ALIGNMENT_CONFLICT.md` — `alignment`/`conflict`
  entre AHF y Wyckoff como diagnósticos (CONTEXT_STATE_NOT_ENTRY_SIGNAL), contrato
  de promoción: requiere evidencia de `EXP-WYCKOFF-ICT-01` (pre-registrado en índice)
  antes de activar FSM Wyckoff completa.

Estos documentos NO implementan código; son la base de diseño para cuando des
luz verde a WYCKOFF-7 (posterior a EXP-WYCKOFF-ICT-01).

## 6. RECLASIFICACIÓN

```
Bloque                          Estado
Replay causal                   ✅
MarketObject persistente        ✅
AHF canónico                    ✅
Setup State                     ✅
6TF                             ✅
FULL/PREFIX                     ✅
Visor mapa trader               ✅
Market State + Wyckoff simul.   ✅ FASE 4.2 PASS (9/9)
EXP-WYCKOFF-ICT-01             ⏭️ siguiente (can_train=false, can_trade=false)
WYCKOFF-7 persistente           ⏭️ posterior (diseño listo, sin impl)
IA / Trading                    ⛔
```

**FASE 4.2 CERRADA.** El visor corregido es 100% causal con ICT + Wyckoff juntos.
Siguiente paso real: `EXP-WYCKOFF-ICT-01` (experimento científico ya pre-registrado).

## 7. SIGUIENTE ACCIÓN

Esperar tu autorización para: (a) push de `5623a7b` + FASE 4.2 + diseños WYCKOFF-7 al
worktree Codex; (b) arrancar `EXP-WYCKOFF-ICT-01` (pre-registrado) cuando lo autoricen.
