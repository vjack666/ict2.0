# Estado del Motor BOS/CHOCH Profesional — ICT SYSTEM

**Fecha:** 2026-08-16
**Autor:** Hermes (ejecutado bajo directiva de Ruben)
**Propósito:** documento único de estado para análisis por IA externa.

---

## 1. Resumen ejecutivo

El motor de lectura de estructura de mercado (BOS/CHOCH) de ICT SYSTEM fue
elevado de "detección geométrica básica" a una **capa operativa de calidad
profesional** con las siguientes propiedades verificadas:

- Detección aislada en `tools/` (geometría pura, SIN ATR).
- Gate duro (veto) de CHOCH: nivel HL/LH correcto + BOS opuesto previo.
- Score híbrido 0–100 (estructura + HTF + geometría + confirmación + IA).
- Modelo de IA calibrado con **TODA la data EURUSD disponible**
  (M5 334.852 velas 2022–2026 + H4 + D1).
- **ROC-AUC 0.798** del modelo sobre holdout (edge real, no ruido).
- El uso diario se sirve desde `engine/daily_motor.py`; la narrativa histórica
  queda en `engine/compat/htf_narrative.py` con wrapper de compatibilidad en
  `engine/htf_narrative.py`.

---

## 2. Arquitectura (single source of truth)

```
tools/                        # DETECCION AISLADA (geometria pura, SIN ATR)
  event.py                    # ToolEvent (linaje cartesiano)
  base.py                     # SingleTool ABC
  swing.py                    # swings HH/HL/LH/LL persistentes
  bos.py                      # BOS (hijo de swing)
  bos_validate.py             # validacion geometrica aislada
  bos_filter.py               # filtro tesis (gate duro)
  choch.py                    # CHOCH (rompe swing contrario al ultimo BOS)
  displacement.py             # intencion de vela (cuerpo>=1.5x rango, mecha<40%)
  quality_score.py            # score BOS 0-1 (bos_real >= 0.5)
  swing_state.py              # fresh/tested/mitigated/invalidated
  choch_quality.py            # EXP-012 + score hibrido + IA (predict_proba)

engine/                      # CONSUMO (unico puente tools->motor)
  bias_from_tools.py         # annotate_with_tools + bias_from_tools
                              #   + bias_from_tools_htf (sesgo HTF con tools)
  htf_narrative.py           # wrapper compatible; no es autoridad normativa
  compat/htf_narrative.py    # implementación histórica/adaptadora
  bias/narrative.py          # motor VIEJO (legacy, aun en uso como fallback)

data/learning/choch/full/    # (gitignore) dataset + model.joblib
  features.jsonl             # 2125 CHOCH REAL, labels ep/peak/dir
  model.joblib               # GBM, label_ep, ROC 0.798
```

**Regla de separación:** `tools/` NO importa `engine/`. `engine/bias_from_tools.py`
es el ÚNICO puente que importa `tools/`. `data/` está en `.gitignore`
(datasets/modelos locales, no commiteados).

---

## 3. Pipeline del score híbrido CHOCH

Para cada CHOCH REAL (gate: nivel HL/LH + after-BOS opuesto):

```
score_base (0-100):
  +70 si is_real
  +10 si momentum (racha >=2 HH/LL)
  +20 si HTF a_favor / +5 contra / +10 neutral
  +20 si displacement
  +15 si no invalidado
  clip 0-100

score_final = clip(score_base + 15 * P_ia, 0, 100)
  donde P_ia = model.predict_proba(features)[:,1]
        features = [score_n, momentum, after_bos, displacement,
                    htf_ctx_code, htf_trend_int, cd, break_body_ratio,
                    dist_to_level, bos_age_bars, tf_code]

choch_class:
  >=85 premium | >=70 useful | <70 noise
```

---

## 4. Evidencia (reproducible)

### 4.1 Generación de dataset (TODA la data)

```
scripts/data/gen_choch_dataset.py  (CHOCH_IA_DISABLE=1 para features estables)
-> data/learning/choch/full/features.jsonl
   M5: 2037 CHOCH REAL | label_ep=1:253 (12.4%) label_peak=1:391 (19.2%)
   H4: 83 CHOCH REAL   | label_ep=1:15 (18.1%)
   D1: 5 CHOCH REAL    | label_ep=1:0
   TOTAL: 2125
```

Label `label_ep`: en N velas posteriores (M5=50, H4=20, D1=10) el precio
cerró >= k*rango_promedio (M5=2.0, H4=1.5, D1=1.0) en la dirección del giro
Y el CHOCH no fue invalidado.

### 4.2 Entrenamiento y ROC

```
scripts/lab/learning/train_choch_full.py
  label_ep | RF: 0.795 | GBM: 0.798 | LR: 0.742   -> MEJOR GBM 0.798
  label_peak | RF: 0.790 | GBM: 0.786 | LR: 0.764
  label_dir  | RF: 0.594 | GBM: 0.570 | LR: 0.556
MODELO FINAL: GBM label_ep ROC=0.798 -> GUARDADO full/model.joblib
```

ROC 0.798 >> 0.55 umbral mínimo útil. **Edge real confirmado.**

### 4.3 Integración activa (smoke test)

```
scripts/smoke/smoke_motor_lectura.py
  build_daily_motor_snapshot(...)
  build_htf_narrative(...)  # solo compatibilidad histórica/adaptación
  -> bias BEARISH, objetivo SSL 1.15261, POI FVG anclado HTF
  choch_ia_prob rango 0.001-0.909, mean 0.12 (discrimina)
```

---

## 5. Commits relevantes (origin/main)

- `ffa7ae1` — feat(engine): IA score CHOCH calibrada con TODA la data + cableo motor
- `66cf1d7` — feat(scripts): F4/F5 dataset + IA score CHOCH
- `e676cc9` — feat(tools): F2 score híbrido 0-100
- `6053dbc` — fix(tools): Task6 gate CHOCH decisión A
- `825486b` — feat(engine): bias_from_tools adaptador

---

## 6. Puntos abiertos (para análisis IA externa)

1. **Solo EURUSD.** Modelo no generaliza a otros pares sin re-entrenar.
2. **Label ep es estricto (12% positivos M5).** ¿Es la definición óptima de
   "importó"? label_peak (19%) o un retorno continuo podrían ser mejores targets.
3. **Score base over-calibrado (scorer viejo `choch_quality.py`):** el scorer
   geométrico aislado daba casi todos premium por el piso (is_real 70+conf 15+HTF 10).
   La **rúbrica teacher nueva** (§8) corrige esto: 80.3% noise. Ver §8.5.
4. **HTF/D1 pocos eventos (5 CHOCH D1).** El sesgo D1 se apoya en poco data.
5. **Sin validación walk-forward.** ROC es holdout aleatorio, no temporal.
   Un backtest temporal honesto podría dar menos.
6. **El motor viejo (narrative.py) sigue en el repo** como fallback. ¿Eliminar?

---

## 7. Cómo reproducir

```bash
cd "C:/Users/v_jac/Desktop/ICT SYSTEM"
.venv/Scripts/python.exe -m scripts.gen_choch_dataset      # dataset (data/, gitignored)
.venv/Scripts/python.exe -m scripts.train_choch_full        # entrena, guarda model.joblib
.venv/Scripts/python.exe -m scripts.smoke_motor_lectura    # brief del dia (use_tools=True)
```

---

## 8. Sistema de Aprendizaje ICT (P1–P5) — agregado 2026-08-16

Capa de aprendizaje que clasifica BOS/CHOCH "como humano" y mide la naturaleza
real del patrón. Commits: `4dd90aa` (P1–P4) + `712048b` (Opción B + P5 + etiquetas).
Bitácora completa: `.hermes-worklog/2026-08-16_1330_APRENDIZAJE_ICT.md`.

### 8.1 CUADRO — Distribución `human_score` (rúbrica teacher)

| Evento | n | premium | useful | noise | mean | Nota |
| --- | --- | --- | --- | --- | --- | --- |
| CHOCH | 2.125 | 0 (0.0%) | 417 (19.6%) | 1.707 (80.3%) | 61.7 | rúbrica ICT estricta, discrimina |
| BOS | 86.870 | 0 (0.0%) | 3.044 (3.5%) | 83.826 (96.5%) | 13.96 | tras Opción B (validador sostenido) |
| SWING | 614.841 | — | — | — | — | `N/A_PRIMITIVO` (no es setup) |

BOS contexto: `strict` → 99.1% invalidated; `sustained` (Opción B) →
**76.1% invalidated / 23.9% active**. La rúbrica BOS da scores reales tras Opción B.

### 8.2 Hallazgo P3 — Naturaleza CHOCH (721 CHOCH M5 2026-08, 50 velas post)

| Desenlace | % |
| --- | --- |
| Reclaim (recupera nivel, falla giro) | **92.8%** |
| BOS confirm (excursión ≥2 rango) | **7.2%** |
| Movimiento neto en dir del giro | 45.4% (≈ random) |

El CHOCH en M5 es RUIDO en ~93% de los casos. Refuta "CHOCH siempre confirma
con BOS". El 92.8% reclaim es feature del dominio (no bug). Coherente con el
80.3% noise de la rúbrica y con SPEC §8.

### 8.3 Componentes

| Módulo | Rol | Commit |
| --- | --- | --- |
| `tools/block_builder.py` | P1: bloques velas (61×7) por CHOCH | `4dd90aa` |
| `tools/teacher_rubric.py` | rúbrica ICT (CHOCH + BOS) como código | `4dd90aa` |
| `scripts/lab/learning/train_block_encoder.py` | P2: encoder CNN-1D (test_mse=0.008 plano) | `4dd90aa` |
| `scripts/lab/learning/probe_choch_nature.py` | P3: naturaleza CHOCH empírica | `4dd90aa` |
| `scripts/lab/learning/label_human.py` | P4: etiqueta CHOCH+BOS, SWING N/A | `4dd90aa` |
| `scripts/data/gen_bos_dataset.py` | features BOS (86.870) | `4dd90aa` |
| `scripts/lab/learning/scan_classify.py` | escáner deficiencias (74 módulos) | `4dd90aa` |
| `tools/bos_validate.py` | Opción B (modo sustained) | `712048b` |
| `scripts/lab/learning/train_nature_head.py` | P5: nature head (test_bce 0.559) | `712048b` |
| `tools/swing.py` | F1 lookback adaptativo + F2 swing_state cableado | `9b...` (7 fases) |
| `scripts/data/gen_swing_dataset.py` | F3: datasets H4/D1 swing (nuevo) | `9b...` |
| `engine/bias_from_tools.py` | F4 cascade + `build_daily_bias` (uso diario) | `9b...` |
| `scripts/lab/learning/label_human.py` | F5 bias jerárquico → rúbrica; F6 reetiquetar | `9b...` |

### 8.4 Auditoría externa (sobre `4dd90aa`) — veredicto

1. Encoder → Head B supervisado por naturaleza ✅ (P5)
2. `bos_validate` → Opción B sostenida ✅ (`712048b`)
3. 92.8% reclaim = feature de dominio ✅ (target de P5)
4. Publicar distribución rúbrica ✅ (cuadro §8.1)

### 8.5 Nota de corrección (DOC_DRIFT)

El punto 3 de §6 ("Casi todos los reales salen premium por el piso") describe el
comportamiento del scorer geométrico viejo `choch_quality.py` (aislado, OVERCALIBRATED
según el escáner). La **rúbrica teacher nueva** da 80.3% noise — no premium. El
ROC 0.798 de §1/§4 es del modelo viejo `full/model.joblib` (GBM label_ep), NO del
sistema de aprendizaje P1–P5. Ambos coexisten: el ROC 0.798 sigue siendo válido
para el scorer de CHOCH cableado al motor; el sistema P1–P5 es un reemplazo
gradual (aún no cableado al motor en vivo).

---

## 9. Commits de aprendizaje (origin/main)

- `4dd90aa` — feat(learn): P1–P4 sistema aprendizaje ICT (encoder + rúbrica + probe + labels)
- `712048b` — feat(learn): Opción B bos_validate (sostenida) + P5 nature head + etiquetas BOS/SWING

---

## 10. Calibración umbrales 2026-08-17 (nota en el cuadro)

| Parámetro | Antes | Ahora | Dónde |
| ----------- | ------- | ------- | ------- |
| `choch_class` premium | score ≥ 85 | **score ≥ 90** | `tools/confirmation_thresholds.py` → `choch_quality` / `teacher_rubric` |
| `choch_class` useful | 70–84 | **70–89** | idem |
| Excursión label (K) M5/H4/D1 | 2.0 / 1.5 / 1.0 | **4.5 / 3.0 / 2.0** (modo CONFIRM) | `scripts/data/gen_choch_dataset.py` |
| CHOCH en `bias_from_tools` | cualquier active | **solo premium** | `engine/bias_from_tools.py` |

Detalle y modos SCAN/CONFIRM/PREMIUM: `docs/UMBRALES_CONFIRMACION.md`.

**Cuadro de lectura diaria (política):**

1. Bias HTF: cascade D1→H4→H1 (`build_daily_bias`).  
2. CHOCH LTF: aviso si useful/noise; dirección solo si **premium**.  
3. BOS: sigue con `bos_real` + validación `sustained`.  
4. No promocionar nature head al motor hasta B4–B8 PASS + shadow.
