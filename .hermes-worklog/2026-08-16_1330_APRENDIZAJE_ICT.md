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
