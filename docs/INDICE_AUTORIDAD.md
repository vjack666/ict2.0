# Índice de Autoridad — ICT SYSTEM

Este archivo define qué documentación es **autoridad vigente** en `ICT SYSTEM`
y qué se dejó deliberadamente fuera de `SMC-SYSTEMS`.

Principio (ver `.hermes.md` §6, §8): **poca documentación, mucha autoridad.**
No reconstruimos `SMC-SYSTEMS` con otro nombre. La tesis ICT completa SÍ se
trajo (autorizada explícitamente 2026-08-15); lo que se dejó fuera es la
arquitectura/historia de SMC-SYSTEMS, no la tesis.

---

## 🟢 Autoridad vigente (tesis ICT completa + diccionarios)

### Fuente firmada (contrato)
| Archivo | Rol | Estado |
|---|---|---|
| `docs/ict/SPEC_TESIS_FORMAL.md` | **Contrato fuente FIRMADO** (comité 2026-07-20). 25 secciones. Resuelve ambigüedades R3 (RR por setup, confirm_bars, POI bonus, exec TF). | Autoridad máxima. Precede al código. |

### Libros de la tesis (narrativa + setups)
| Archivo | Rol |
|---|---|
| `docs/ict/00_INDICE.md` | Índice de la biblioteca ICT. |
| `docs/ict/01_KILLZONES.md` | Ventanas horarias (London/NY AM/PM). |
| `docs/ict/02_MSS_CHOCH.md` | MSS / CHOCH / BOS. |
| `docs/ict/03_FVG.md` | Fair Value Gap. |
| `docs/ict/04_ORDER_BLOCKS.md` | Order Blocks. |
| `docs/ict/05_LIQUIDEZ.md` | Liquidez / Sweep. |
| `docs/ict/06_TURTLE_SOUP.md` | Turtle Soup (contratendencia). |
| `docs/ict/07_SILVER_BULLET.md` | Silver Bullet (scalping). |
| `docs/ict/08_POWER_OF_THREE.md` | PO3 / AMD (ciclo A/M/D). |
| `docs/ict/14_STOP_LOSS_ESTRUCTURAL.md` | SL estructural. |
| `docs/ict/15_INTRADIA_ENTRADA_SL_TP.md` | Entrada/SL/TP intradía. |
| `docs/ict/16_TEMPORALIDAD_EJECUCION.md` | Temporalidad de ejecución. |
| `docs/ict/17_SCALPING_ENTRADA_SL_TP.md` | Scalping entry/SL/TP. |
| `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md` | 3 capas HTF/ITF/exec, regla dura de SL/entry. |
| `docs/ict/20_TESIS_ICT.md` | Síntesis unificadora PO3+liquidez+temporalidad+POI. |
| `docs/ict/21_POI.md` | Point of Interest (PD Array anclado a narrativa). |

### Hallazgos y SDD de tesis
| Archivo | Rol |
|---|---|
| `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` | Evidencia de estructura. |
| `docs/tesis/HALLAZGOS_SESGO_BACKTEST.md` | Evidencia de sesgo. |
| `docs/tesis/PLAN_RESCATE_POI_HTF.md` | Plan de rescate POI HTF. |
| `docs/tesis/SDD_LTF_ENTRY_LAYER.md` | SDD de capa de entrada LTF. |
| `docs/tesis/SDD_M2_LINEAGE.md` | SDD de lineage M2. |
| `docs/tesis/SDD_RESCATE_POI_HTF.md` | SDD de rescate POI HTF. |

### Diccionarios de detección
| Archivo | Rol |
|---|---|
| `docs/reglas/ICT_RULEBOOK.md` | Diccionario *machine-readable* de detección ICT (BOS/CHOCH/FVG/OB/sweep/displacement/premium-discount/OTE/MTF). |
| `docs/reglas/WYCKOFF_RULEBOOK.md` | Diccionario de detección Wyckoff. |
| `docs/wyckoff/**` | Teoría Wyckoff completa. |

**Jerarquía de autoridad:** `SPEC_TESIS_FORMAL.md` es la fuente firmada que
UNIFICA los libros 01-21. Ante contradicción, **el SPEC manda** (ver abajo).
Los libros son la explicación narrativa; el SPEC es el contrato ejecutable.

---

## 🔴 Dejada (arquitectura / histórico de SMC-SYSTEMS — NO entra)

Esto NO es tesis; es diseño de software / proceso / historia del repo viejo:

- `docs/ict/SDD_ICT_BACKTEST.md`, `SDD_REFACCION_2026-07-11.md` — SDD del repo viejo.
- `docs/ict/API_SPEC.md`, `TEST_PLAN.md` — API/tests de SMC-SYSTEMS.
- `docs/ict/09_OPTIMIZADOR_BAYESIANO.md` — anexo de validación, no tesis.
- `docs/ict/10_AUDITORIA_REFACCION/**`, `13_BACKTEST_PROFESIONAL/**` — auditorías/procesos viejos.
- `docs/ict/10_SWEEP_OTE_FILTRO.md`, `11_SWEEP_OTE_MANUAL_VS_AUTO.md` — filtros de implementación vieja.
- `docs/ict/12_ESTRATEGIAS_COMPLETAS.md` — inventario de código (`rules.py`/`engine.py`). Arquitectura disfrazada.
- `docs/ict/_PLANTILLA_LIBRO.md` — meta-plantilla de SMC-SYSTEMS.
- `docs/_archivo/**`, `docs/_descartado/**`, `docs/architecture/**`, `docs/specs/**` (SDD/MDS), `docs/plan/**`, `docs/planificacion/**` — historia/arquitectura obsoleta.
- `research/`, `openspec/`, `knowledge/`, `results/`, `graphify-out/`, `tests/QUARANTINE.md` — capa científica/experimental de SMC-SYSTEMS.

---

## Discrepancias conocidas (resueltas por el SPEC — el SPEC manda)

| Tema | Libro / ICT_RULEBOOK | SPEC_TESIS_FORMAL | Veredicto |
|---|---|---|---|
| RR mínimo | libro 07 = 1:2; libro 18 = 1:3 | §20: SB=1:2, resto=1:3 (por setup) | **SPEC** |
| POI | libro 21 §0 = "obligatorio" | §16: BONUS `quality_score+=20`, no gate | **SPEC** (evidencia PF 0.900 vs 1.511) |
| OTE retrace | ICT_RULEBOOK §9 = 68-80% | §21 = 62-79% | **SPEC** (código usa 62-79%) |

---

*Mantenido por Hermes. Cualquier nuevo documento en `docs/` debe justificar
por qué es autoridad vigente, no solo "parece importante" (.hermes.md §8).*
