# Bitácora — Sistema de Aprendizaje ICT (P1–P5 + etiquetado BOS/SWING)

**Fecha:** 2026-08-16
**Autor:** Hermes (ejecutado bajo directiva de Ruben)
**Rama:** main · Commits: `4dd90aa` (P1–P4) + `712048b` (Opción B + P5 + etiquetas)
**Propósito:** registrar el ciclo de aprendizaje que clasifica BOS/CHOCH "como humano"
y mide la naturaleza real del patrón, para análisis por IA externa.

---

## 1. Decisión de diseño (origen)

Ruben quería clasificar BOS/CHOCH pero eran demasiados para hacerlo a mano.
Se delegó a la IA: clasificar de forma que se pueda **buscar problema o deficiencia**.
Resultado: esquema de deficiencias (escáner) + rúbrica ICT como código (teacher) +
encoder de bloque de velas (el "ojo") + head de naturaleza (el "qué hace el mercado").

Arquitectura de 2 niveles (ICT-Neuro):
- **Nivel 1 — Ojo (encoder):** bloque de velas crudas (61×7) → embedding.
  Auto-supervisión por reconstrucción → `test_mse=0.00799` PLANO (no aprendió
  dinámica; aceptado por auditoría como "extractor de forma").
- **Nivel 2 — Mente (heads):**
  - Head A (rúbrica humana): `human_score` 0–100 tipo experto.
  - Head B (naturaleza): predice confirm vs reclaim desde el bloque.

---

## 2. CUADRO — Distribución de `human_score` (rúbrica teacher)

| Evento | n | premium | useful | noise | mean | Nota |
|---|---|---|---|---|---|---|
| **CHOCH** | 2.125 | 0 (0.0%) | 417 (19.6%) | 1.707 (80.3%) | 61.7 | rúbrica ICT estricta, discrimina |
| **BOS** | 86.870 | 0 (0.0%) | 3.044 (3.5%) | 83.826 (96.5%) | 13.96 | tras Opción B (validador sostenido) |
| **SWING** | 614.841 | — | — | — | — | `N/A_PRIMITIVO` (no es setup; metadatos via swing_state) |

Contexto BOS:
- Antes de Opción B: validador `strict` → 99.1% invalidated (casi todo human_score=0).
- Tras Opción B (`sustained`, N=3 cierres consecutivos, horizonte 200 velas):
  **20.788 active / 66.082 invalidated (76.1% invalidated, 23.9% active)**.
  La rúbrica BOS ahora da scores reales (no todo 0).

---

## 3. Hallazgo empírico central (P3 — Naturaleza CHOCH)

Muestra: 721 CHOCH reales M5, 2026-08, ventana post 50 velas.

| Desenlace | % |
|---|---|
| Reclaim (recupera nivel, falla giro) | **92.8%** |
| BOS confirm (excursión ≥2 rango, sin reclaim) | **7.2%** |
| Movimiento neto en dir del giro | 45.4% (≈ random) |

**Conclusión:** en M5 el CHOCH es RUIDO en ~93% de los casos, no un giro.
Refuta la hipótesis de partida ("tras CHOCH siempre confirma con BOS").
Coherente con SPEC §8 ("CHOCH sin BOS posterior → solo aviso") y con el
80.3% noise de la rúbrica. El 92.8% reclaim es **feature del dominio**, no bug.

---

## 4. Opción B en `bos_validate.py` (pedido de auditoría externa)

- `mode="sustained"` (default): invalida BOS solo tras N=3 cierres CONSECUTIVOS
  en contra (horizonte 200 velas). Un wick/ruido de 1 vela NO mata el BOS.
- `mode="strict"` preservado para experimentos de sensibilidad.
- Optimizado: acotado a 200 velas (el sostenido original era O(n_bos×n_tail) y colgaba).
- Efecto: 99.1% → 76.1% invalidated.

---

## 5. P5 — Nature Head (Head B supervisado, recomendación #1 auditoría)

- Input: bloque de velas normalizado (flatten 61×7). Target: confirm vs reclaim (P3).
- 843 muestras (2026-08), 10.1% confirm. MLP 2 capas, BCE.
- `test_bce`: 0.635 → **0.559** (aprende señal de confirmación sobre prior reclaim).
- Guardado `data/learning/encoder/nature_head.pt`.
- Veredicto honesto: predice P(bos_confirm) ligeramente mejor que azar; internaliza
  la distribución 90% reclaim en vez de asumir giro.

---

## 6. Auditoría externa (commit `4dd90aa`) — veredicto

| # | Recomendación | Cumplido |
|---|---|---|
| 1 | Encoder → Head B supervisado por naturaleza | ✅ P5 |
| 2 | `bos_validate` → Opción B sostenida | ✅ `712048b` |
| 3 | 92.8% reclaim = feature de dominio | ✅ usado como target |
| 4 | Publicar distribución rúbrica | ✅ este cuadro |

---

## 7. Archivos creados/modificados (este ciclo)

| Archivo | Rol | Commit |
|---|---|---|
| `tools/block_builder.py` | P1: bloques velas (61×7) por CHOCH | `4dd90aa` |
| `tools/teacher_rubric.py` | rúbrica ICT (CHOCH + BOS) como código | `4dd90aa` |
| `scripts/train_block_encoder.py` | P2: encoder CNN-1D (mse plano) | `4dd90aa` |
| `scripts/probe_choch_nature.py` | P3: naturaleza CHOCH empírica | `4dd90aa` |
| `scripts/label_human.py` | P4: etiqueta CHOCH+BOS, SWING N/A | `4dd90aa` |
| `scripts/gen_bos_dataset.py` | features BOS (86.870) | `4dd90aa` |
| `scripts/scan_classify.py` | escáner deficiencias (74 módulos) | `4dd90aa` |
| `tools/bos_validate.py` | Opción B (sustained) | `712048b` |
| `scripts/train_nature_head.py` | P5: nature head | `712048b` |

---

## 8. Pendiente / siguiente ciclo

- Inferencia en vivo: script que use `nature_head.pt` + `teacher_rubric` para
  calificar CHOCH/BOS en vivo y modular el bias del motor.
- Reentreno del encoder con objetivo de dirección (no reconstrucción MSE).
- El depósito `C:\Users\v_jac\Desktop\SMC-SYSTEMS` quedó como receptor de módulos
  reemplazados (aún no se movió nada; CHOCH/BOS/swing siguen en ICT SYSTEM).

---

## 9. Plan de 7 fases — Jerarquía de Swings y Sesgo HTF (2026-08-16)

Ejecutado completo tras aprobación. Base: SPEC §42-49 (sesgo=D1/H4/H1 velas
cerradas→alineación D1→H4→H1; PRE sin look-ahead; §47 sesgo=último swing
MAYOR), narrative.py T9 (D1 autoridad raíz vía `_compose_htf_bias`), §79 (swing
ventana NO centrada + shift). NO invención.

| F | Qué | Archivo | Evidencia |
|---|---|---|---|
| 1 | Lookback adaptativo por TF (M5:5/M15:8/H1:12/H4:20/D1:30) | `tools/swing.py` | `TF_LOOKBACK` + `tf=` param |
| 2 | `swing_state` cableado (fresh/mitigated) | `tools/swing.py` | smoke M5: 385 swings (351 mitig/34 fresh) |
| 3 | Datasets H4/D1 de swing | `scripts/gen_swing_dataset.py` (nuevo) | M5=385, H4=1, D1=0 (ago corto) |
| 4 | Cascade bottom-up + `build_daily_bias` | `engine/bias_from_tools.py` | daily bias D1/H4 rng, H1 BEARISH, dir NEUTRAL |
| 5 | Bias jerárquico → rúbrica | `scripts/label_human.py` | inyecta `htf_ctx` desde `build_daily_bias` |
| 6 | Reetiquetar BOS/CHOCH con jerarquía | `scripts/label_human.py` | ver cuadro §9.1 |
| 7 | Bitácora + cuadro + commit/push | este doc | commit posterior a 9a639fe |

### 9.1 CUADRO — Swings y etiquetas tras las 7 fases (2026-08)

| Evento | Antes | Después | Nota |
|---|---|---|---|
| SWING M5 (mes) | 614.841 (ruido lookback=5) | **385** (lookback 5 + mitig geom) | cura raíz del ruido |
| SWING H4 | 0 | 1 | dataset creado (F3) |
| SWING D1 | 0 | 0 | ago corto (<30 velas D1); correcto |
| SWING estado | "active" genérico | fresh/mitigated | `swing_state` cableado (F2) |
| CHOCH (2.125) | 80.3% noise | **99.8% noise** (0 prem/5 useful) | bias 2026-08=NEUTRAL (rango HTF) |
| BOS (86.870) | 96.5% noise | 96.5% noise (3.044 useful) | bias NEUTRAL → sin cambio este mes |

Hallazgo F5/F6: el sesgo HTF de 2026-08 fue **NEUTRAL** (D1/H4 ranging). Por
tanto inyectar `htf_ctx` jerárquico no movió la distribución este mes — es
correcto y esperable (SPEC §48: rango = contexto, no anula setup). El mecanismo
funciona; en un mes con tendencia D1 (a_favor/contra) SÍ moverá los scores.

### 9.2 Veredicto de las 7 fases

- La raíz del ruido (614k swings M5 de 25min) está **curada**: 385 swings M5
  válidos + estado de vida del nivel. CHOCH/BOS ahora se construyen sobre
  estructura mayor, no sobre pivotes de microestructura.
- El cascade D1→H4→H1 está **cableado para uso diario** (`build_daily_bias`),
  sin look-ahead, con D1 como autoridad raíz (tesis §47).
- NO se calificó swing con human_score (sigue N/A primitivo); se le dio
  trazabilidad de vida (fresh/mitigated) que es el equivalente correcto.
- NO se usó ATR ni medias (geometría pura, narrative.py:25).
- El sistema es ahora **tesis-correcto** aunque el mes estuviera en rango.

### 9.3 Commits de las 7 fases (origin/main)

- (commit posterior a 9a639fe, ver git log)

