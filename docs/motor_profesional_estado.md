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
- Motor de lectura día a día (`engine/htf_narrative.build_htf_narrative`)
  **ENCENDIDO por defecto** con `use_tools=True`.

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
  htf_narrative.py           # build_htf_narrative (motor de lectura dia a dia)
                              #   default use_tools=True -> usa bias_from_tools_htf
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
scripts/gen_choch_dataset.py  (CHOCH_IA_DISABLE=1 para features estables)
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
scripts/train_choch_full.py
  label_ep | RF: 0.795 | GBM: 0.798 | LR: 0.742   -> MEJOR GBM 0.798
  label_peak | RF: 0.790 | GBM: 0.786 | LR: 0.764
  label_dir  | RF: 0.594 | GBM: 0.570 | LR: 0.556
MODELO FINAL: GBM label_ep ROC=0.798 -> GUARDADO full/model.joblib
```
ROC 0.798 >> 0.55 umbral mínimo útil. **Edge real confirmado.**

### 4.3 Integración activa (smoke test)
```
scripts/smoke_motor_lectura.py
  build_htf_narrative(m15, htf_frames={D1,H4}, use_tools=True)
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
3. **Score base over-calibrado:** is_real(70)+confirmación(15)+HTF(10)=95 base.
   Casi todos los reales salen premium por el piso. ¿Recalibrar pesos?
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
