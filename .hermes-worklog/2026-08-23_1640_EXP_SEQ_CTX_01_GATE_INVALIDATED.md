# Bitácora — EXP-SEQ-CTX-01: construcción + gate causal INVALIDATED

**Fecha:** 2026-08-23 16:40 UTC-5
**Autor:** Hermes (jefe de laboratorio)
**Rama:** feature/a5-audit-datos
**Objetivo del Director:** identificar y validar qué secuencias ICT cambian
significativamente su comportamiento según el Context State
(ALIGNED/NEUTRAL/AGAINST), con evidencia PIT, muestra suficiente y SIN PnL ni
optimización de trading.

---

## Qué se construyó (ordenado, sin duplicar el experimento fallido previo)

EXP-SEQ-CTX-01 es un rediseño limpio de `EXP_SEQUENCE_X_CONTEXT_STATE`
(v1 `INSUFFICIENT_N`, v2 `INVALIDATED` por leakage de secuencias). Esta vez el
motor de secuencias v2 causal ya estaba mergeado, así que el diseño usó el
navigator causal directamente.

| Artefacto | Ruta |
|---|---|
| Gate causal (barrera) | `scripts/lab/experiments/exp_seq_ctx_01_gate.py` |
| Matriz S×Context (no ejecutada) | `scripts/lab/experiments/exp_seq_ctx_01.py` |
| Diagnóstico de raíz | `scripts/lab/experiments/exp_seq_ctx_01_diag_root.py` |
| Diseño/doc | `docs/experimentos/EXP_SEQ_CTX_01.md` |
| Salida gate | `reports/audits/experiments/seq_ctx_01/gate_causal.json` |

Todo 100% LOCAL (Python sistema `C:/Python314/python.exe`, CSV Dukascopy 20Y,
sin nube). Limpieza: borrados 2 logs huérfanos `.hermes-state/logs/exp_seqxcontext.*.log`
(acumulación del 2026-08-20).

---

## Veredicto del gate causal — **INVALIDATED**

`exp_seq_ctx_01_gate.py` sobre H1 20Y (120 barras muestra determinista,
full-vs-prefix): **31/120 violaciones** → el motor de navegación **NO es
point-in-time estable** en la ruta que usa el experimento.

La matriz (`exp_seq_ctx_01.py`) está programada para **ABORTAR** si
`gate_causal.json` no dice `PASS` (barrera cumplida). No se corrió, no se
interpretaron números falsos (anti-p-hacking).

## Raíz del leakage (confirmada con diff reproducible, no por descarte)

- Campos que divergen: `layers.H1.structure_bias` y `layers.H1.regime`
  (y `regime_stack.H1`), todas en la capa H1. También `n_zones` ±1.
- Test aislado (`exp_seq_ctx_01_diag_root.py`): swings **altos** (`sh`)
  idénticos FULL vs PREFIX (274=274). Swings **bajos** (`sl`) difieren en
  longitud: **FULL=262 vs PREFIX=261** (un swing bajo existe en FULL, no en PREFIX).
- Mecanismo: `_causal_swings` (engine/mtf_navigation.py ~L256) usa **ventana
  centrada** `j-left .. j+left+1` que mira `left` barras al FUTURO. En PREFIX,
  cerca del borde del df truncado faltan esas barras → el swing no se forma →
  `sl` diverge → `structure_bias` (BEARISH vs MIXED) y `regime` divergen.
- **NO es** el bug de `_build_eq_pools` de secuencias arreglado en v2 (ese pasa
  su propio gate). Es deuda DISTINTA, en el motor de navegación MTF (capa H1).

## Consecuencia

- El diseño del experimento es correcto; el **motor subyacente** tiene leakage
  en H1. EXP-SEQ-CTX-01 queda SUSPENDIDO hasta cerrar la raíz.
- Próximo paso requiere decisión del Director (toca infraestructura validada
  funnel/TNA):
  1. **Fix en `_causal_swings`** (ventana solo-pasado) + re-correr gate + revalidar
     funnel 20Y y TNA.
  2. **Aislar el EXP** con PREFIX reales por barra (`SEC_PIT_WITHIN_RANGE`, como
     la v2 del 2026-08-20), asumiendo su deuda documentada. No recomendado
     mientras el gate del navigator falle.

---

## Actualización de índices

- `.hermes-index.md` → Cuadro de mando: fila EXP SEQUENCE×CONTEXT (legado) +
  nueva fila EXP-SEQ-CTX-01 (SUSPENDIDO, gate INVALIDATED). Estado general
  actualizado a 2026-08-23.
- Grafo graphify actualizado (`graphify update .`).

## Commit

Solo los archivos de este experimento + índice + bitácora (no se mezcla trabajo
ajeno sin commitear). Mensaje: `feat(lab): EXP-SEQ-CTX-01 gate causal INVALIDATED — raíz leakage _causal_swings H1 [CERTIFICAR]`.
