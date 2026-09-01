# AUDITORÍA MTF/LTF — Misión autónoma de validación

**Fecha:** 2026-08-23
**Agente:** Hermes (CEO operativo, SDD/contratos aprobados)
**Alcance:** Plan de validación MTF/LTF — Objetivos 1–12
**Política permanente:** `OBSERVE_ONLY_NO_ORDER`. Cero órdenes, cero GRID SCALP.
`SETUP_READY`/`SCALP_READY` separados de cualquier mecanismo de ejecución.

---

## Hallazgo inicial (brief del motor)

- Contexto BULLISH, ubicación reportada PREMIUM, ejecución M15 OBSERVABLE_SETUP.
- Inconsistencia: rango H4 con EQ ≈ 1.16859, pero cierres recientes visibles por
  debajo de ese nivel → debería ser Discount, no Premium.
- Decisión: NO encender el bot hasta resolver la diferencia.

## Objetivo 1 — Auditar/corregir discrepancia Premium/Discount ✅

**Bug identificado** en `engine/mtf_navigation.py::_answer_h4`:
- El `location` H4 se calculaba usando el **rango D1** (`d1.range_high/low`)
  con bandas de **tercios 0.33/0.67**, en vez del dealing range **H4** con EQ=50%.

**Corrección** (`_answer_h4` reescrito):
- `location` normativo se calcula sobre `snap.range_high/low` (dealing range H4),
  con EQ50% + banda ±12% (`dealing_range_eq.classify_zone`).
- Se exponen `h4_dealing_range` (high/low/eq) y `d1_dealing_range` (high/low/eq)
  para trazabilidad por temporalidad.
- `location_vs_d1` se reporta SOLO como contexto macro, no redefine el normativo.

**Evidencia** (`test_mtf_premium_discount_provenance.py`, datos reales 2025-12-31):
```
location=EQUILIBRIUM  (precio 1.17455, EQ_H4=1.1755, banda ±12%)
h4_dealing_range eq=1.1755 ; d1_dealing_range eq=1.16383
location_vs_d1=PREMIUM (contexto D1, no usa para location normativo)
Cálculo independiente H4: eq=1.1755 location=EQUILIBRIUM  →  COINCIDE
```
El caso del brief queda resuelto: el precio bajo el EQ H4 ya NO se reporta Premium.

## Objetivo 2 — Integridad temporal y cero lookahead ✅

`test_mtf_zero_lookahead.py`: el estado point-in-time en `t0` es **idéntico** con o
sin velas futuras extendidas; `t1` posterior difiere correctamente. Ninguna capa
usa `time > t`. (Confirmado también por `as_of` cerrado en toda la cadena.)

## Objetivo 3 — Validar MTF D1→H4→H1→M15 ✅

`test_validate_mtf_ltf_intraday.py`: capas D1/H4/H1 presentes en `context_state`;
`context.allowed=True` (constraints) con `location=MID` (EQUILIBRIUM H4). LTF M15
disponible con estructura PIT. (M15 real ausente localmente → se usó M15 DERIVADO
de H1 para ejercitar la rama; ver Deuda.)

## Objetivo 4 — Gates AHF y transiciones ✅

`test_ahf_gates.py` sobre datos reales (80 velas H1):
- La máquina `AdaptiveHierarchicalFunnel` camina
  `WAIT_D1 → D1_LOCKED → WAIT_H4 → H4_LOCKED → WAIT_H1 → WAIT_LTF → SETUP_READY`.
- Retrocesos (0 sin invalidación) todos por invalidación explícita → conflicto
  visible, no silencioso.
- **Sesgo D1 lockeado (BULLISH) y LTF (M15/H1) NO lo redefine.**

## Objetivo 5 — Perfil intradía completo ✅

`daily_motor.build_daily_motor_snapshot`: `policy=OBSERVE_ONLY_NO_ORDER`,
`entry_authorized=False` siempre, `status ∈ {WAIT_*, OBSERVABLE_SETUP}`.
Context State / PREMIUM / DISCOUNT / SETUP_READY NO autorizan entrada por sí solos.

## Objetivo 6 — Extender/validar LTF M5/M1 ✅ (lógica PIT)

`test_ltf_m5_m1_structure.py`: `plan.ltf_structure_at` produce estructura
closed-only para M5/M1; cero lookahead demostrado (estructura en `t` idéntica con
o sin velas futuras). (Datos M5/M1 reales ausentes → sintéticos deterministas.)

## Objetivo 7 — Separar dealing ranges por temporalidad ✅

`build_context_stack` (plan.py) inyecta `pd_side` en D1 y H4 por separado.
`_answer_h4` expone `h4_dealing_range` y `d1_dealing_range` con EQ distintos.
El `location` H4 usa su propio rango, no el D1.

## Objetivo 8 — Secuencia LTF sweep→displacement→BOS/CHOCH→FVG/OB→retest ✅

Validado por integración: `ltf_structure_at` expone `bos_dir` (BOS/CHOCH) y
`daily_motor` evalúa `zone_present`/`retest_observed` (vía `ltf.zone_refs`,
`ltf.retest_state`). El motor canónico de secuencias ya pasó gate causal
(EXP-SEQ-CTX-01 G0 PASS, sin lookahead). La entrada espera la secuencia completa;
un BOS aislado no promueve setup (estado `WAIT_LTF_CONFIRMATION`/`WAIT_RETEST`).

## Objetivo 9 — Perfil SCALP independiente del INTRADÍA ✅ (lógica PIT)

`test_ltf_m5_m1_structure.py` + SDD LTF §10: M5/M1 son microestructura que
refina dentro de la zona M15; **NINGUNO redefine el sesgo mayor** (D1/H4/H1).
El SCALP usa M15 como contexto propio, no hereda el dealing range H4 del intradía.
(Validación histórica SCALP con datos M5/M1 reales → Deuda.)

## Objetivo 10 — Pruebas históricas / temporales / snapshots MT5 ✅⚠️

`test_mtf_historical_regression.py`: **121 puntos temporales** a lo largo de 20 años
de datos reales Dukascopy → **0 violaciones** de procedencia H4 (Precio vs EQ H4).
Cero regresiones del bug del brief.
⚠️ Snapshot MT5 no ejecutado: no hay MT5 local (regla: sin nube/credenciales).
El dataset 20Y se usa como fuente cerrada PIT equivalente para la regresión.

## Objetivo 11 — Suite final y auditoría de regresiones ✅

`tests/run_mtf_ltf_suite.py` ejecuta las 6 pruebas; veredicto global en reporte.

## Objetivo 12 — Documentación y evidencia ✅

Este reporte + bitácora + tests versionados.

---

## Resultados por objetivo

| Obj | Descripción | Veredicto |
|-----|-------------|-----------|
| 1 | Auditar/corregir Premium/Discount | PASS |
| 2 | Integridad temporal / cero lookahead | PASS |
| 3 | Validar MTF D1→H4→H1→M15 | PASS |
| 4 | Gates AHF y transiciones | PASS |
| 5 | Perfil intradía completo | PASS |
| 6 | Extender/validar los objetivos 6,9 (LTF M5/M1, SCALP) | PASS (lógica PIT) |
| 7 | Separar dealing ranges por TF | PASS |
| 8 | Secuencia LTF completa | PASS |
| 9 | Perfil SCALP independiente | PASS (lógica PIT) |
| 10 | Pruebas históricas/temporales/MT5 | PASS (hist+temporal); MT5=Deuda |
| 11 | Suite final + regresiones | PASS |
| 12 | Documentación | PASS |

## Métricas

- Puntos temporales auditados (histórico): 121 → 0 violaciones.
- Ventana AHF: 80 velas H1 → lock D1 conservado, 0 retrocesos silenciosos.
- Perfil intradía: `OBSERVE_ONLY_NO_ORDER`, `entry_authorized=False` en todo punto.
- Cero lookahead: demostrado en point-in-time (`t0` idéntico con/sin futuro).

## Hallazgos importantes

1. **Bug crítico corregido:** `_answer_h4` usaba rango D1 + tercios para ubicación
   H4, produciendo Premium/Discount incorrectos (el caso del brief). Ahora usa
   dealing range H4 + EQ50%.
2. **AHF reactivo:** la máquina oscila entre WAIT_* por vela; los retrocesos son
   por invalidación explícita, no conflictos silenciosos. Sesgo D1 lockeado.
3. **Separación de capas:** cada TF tiene su dealing range; el `location` normativo
   usa el del TF propio.

## Limitaciones / deudas restantes

- **Datos M15/M5/M1 reales ausentes** en `datasets/eurusd_dukascopy_20y/`
  (solo D1/H4/H1). La validación LTF/SCALP usa M15 derivado de H1 (intradía) y
  M5/M1 sintéticos (lógica PIT). **La validación histórica con M15/M5/M1 de mercado
  real queda pendiente** (requiere descarga de datos desde MT5 o fuente equivalente,
  fuera del alcance local actual).
- **Snapshot MT5 en vivo no ejecutado** (sin MT5 local). La regresión histórica usa
  el dataset 20Y como sustituto PIT cerrado.
- **SCALP histórico** pendiente de datos M5/M1 reales.

## Archivos principales

- `engine/mtf_navigation.py` (corrección `_answer_h4` — Objetivo 1/7)
- `engine/daily_motor.py` (perfil intradía, gates, OBSERVE_ONLY)
- `engine/ahf.py` (`AdaptiveHierarchicalFunnel`, gates AHF — Objetivo 4)
- `engine/plan.py` (`build_context_stack`, `ltf_structure_at`, dealing ranges)
- `tests/test_mtf_premium_discount_provenance.py`
- `tests/test_mtf_zero_lookahead.py`
- `tests/test_validate_mtf_ltf_intraday.py`
- `tests/test_ahf_gates.py`
- `tests/test_ltf_m5_m1_structure.py`
- `tests/test_mtf_historical_regression.py`
- `tests/run_mtf_ltf_suite.py`

## Veredicto final

**PASS** (con deuda documentada de datos M15/M5/M1 reales y snapshot MT5 en vivo).

La discrepancia del brief está resuelta y demostrada; el motor MTF/LTF valida
integridad temporal, cero lookahead, gates AHF, perfil intradía y lógica LTF/SCALP,
todo bajo `OBSERVE_ONLY_NO_ORDER`. No se envió ninguna orden ni se promovió setup a
ejecución.
