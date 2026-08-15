# Índice de Autoridad — ICT SYSTEM

Este archivo define qué documentación es **autoridad vigente** en `ICT SYSTEM`
y qué se dejó deliberadamente fuera de `SMC-SYSTEMS`.

Principio (ver `.hermes.md` §6, §8): **poca documentación, mucha autoridad.**
No reconstruimos `SMC-SYSTEMS` con otro nombre.

---

## 🟢 Autoridad vigente (migrada de SMC-SYSTEMS)

| Archivo | Rol | Estado |
|---|---|---|
| `docs/ict/SPEC_TESIS_FORMAL.md` | **Contrato fuente FIRMADO** (comité 2026-07-20). 25 secciones. Resuelve ambigüedades R3 (RR por setup, confirm_bars, POI bonus, exec TF). | Autoridad máxima. Precede al código. |
| `docs/reglas/ICT_RULEBOOK.md` | Diccionario *machine-readable* de detección de conceptos ICT (BOS/CHOCH/FVG/OB/sweep/displacement/premium-discount/OTE/MTF). | Autoridad de detección. |
| `docs/reglas/WYCKOFF_RULEBOOK.md` | Diccionario de detección Wyckoff (Spring/UTAD/SOS/SOW/LPS/LPSY/effort-result). | Autoridad de detección. |
| `docs/wyckoff/**` | Teoría Wyckoff completa (leyes, fases buyside/sellside, volumen, relación ICT). | Conocimiento vigente. |

**Estas 4 piezas son la única fuente documental del sistema.** Cualquier
afirmación de estrategia debe trazarse a `SPEC_TESIS_FORMAL.md`.

---

## 🔵 Referencia (NO migrada — queda en SMC-SYSTEMS)

Libros `docs/ict/01-21` (Killzones, MSS, FVG, OB, Liquidez, Turtle Soup,
Silver Bullet, PO3, estrategias, SL/entry/TP, temporalidad, POI, etc.).

**Por qué no entran:** el `SPEC_TESIS_FORMAL.md` ya los unifica y FIRMA como
contrato. Son *inputs* del SPEC, no autoridad adicional. Si se necesita la
explicación pedagógica de un componente, se consulta en `SMC-SYSTEMS`, pero el
nuevo sistema no los ejecuta como contrato.

Excepciones de conocimiento ya absorbidas por el SPEC (no hace falta migrarlas):
- Ciclo PO3/AMD → `SPEC §19`
- Regla dura 3-capas HTF/ITF/exec → `SPEC §9/§10`
- 5 condiciones Silver Bullet → `SPEC §17`
- 8 reglas POI (3 condiciones, tiers, stacking, invalidación) → `SPEC §16`
- Horarios Killzone → `SPEC §15`

---

## 🔴 Dejada (arquitectura / histórico de SMC-SYSTEMS — NO entra)

- `docs/ict/SDD_ICT_BACKTEST.md`, `SDD_REFACCION_2026-07-11.md` — SDD del repo viejo.
- `docs/ict/API_SPEC.md`, `TEST_PLAN.md` — API/tests de SMC-SYSTEMS.
- `docs/ict/10_AUDITORIA_REFACCION/**`, `13_BACKTEST_PROFESIONAL/**` — procesos/auditorías viejas.
- `docs/ict/10_SWEEP_OTE_FILTRO.md`, `11_SWEEP_OTE_MANUAL_VS_AUTO.md` — filtros de implementación vieja.
- `docs/ict/12_ESTRATEGIAS_COMPLETAS.md` — inventario de código (`rules.py`/`engine.py`). Arquitectura disfrazada.
- `docs/ict/09_OPTIMIZADOR_BAYESIANO.md` — anexo de validación, no estrategia.
- `docs/_archivo/**`, `docs/_descartado/**`, `docs/architecture/**`, `docs/specs/**` (SDD/MDS), `docs/plan/**`, `docs/planificacion/**` — historia/arquitectura obsoleta.
- `research/`, `openspec/`, `knowledge/`, `results/`, `graphify-out/`, `tests/QUARANTINE.md` — capa científica/experimental de SMC-SYSTEMS.

---

## ⚫ Fuera del pensamiento

Índices y plantillas de SMC-SYSTEMS (`docs/ict/00_INDICE.md`, `_PLANTILLA_LIBRO.md`)
no tienen valor para el nuevo sistema.

---

## Discrepancias conocidas (resueltas por el SPEC)

| Tema | ICT_RULEBOOK / libro | SPEC_TESIS_FORMAL | Veredicto |
|---|---|---|---|
| RR mínimo | libro 07 = 1:2; libro 18 = 1:3 | §20: SB=1:2, resto=1:3 (por setup) | **SPEC manda** |
| POI | libro 21 §0 = "obligatorio" | §16: BONUS `quality_score+=20`, no gate | **SPEC manda** (evidencia PF 0.900 vs 1.511) |
| OTE retrace | ICT_RULEBOOK §9 = 68-80% | §21 = 62-79% | **SPEC manda** (código usa 62-79%) |

---

*Mantenido por Hermes. Cualquier nuevo documento en `docs/` debe justificar
por qué es autoridad vigente, no solo "parece importante" (.hermes.md §8).*
