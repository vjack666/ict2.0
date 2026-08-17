# Bitácora — Calibración umbrales de confirmación (BOS/CHOCH/score)

**Fecha:** 2026-08-17 13:00 UTC-5  
**Autor:** Grok (bajo directiva de Ruben) + evidencia Hermes  
**Rama:** main  
**Estado:** APLICADO en código (shadow-ready; bias solo premium)

---

## 1. Objetivo

Calibrar umbrales de confirmación para mejorar calidad de lectura BOS/CHOCH/SWING
en M15/H1/H4/D1 sin contaminar el log de aprendizaje (modo SCAN preservado).

## 2. Evidencia

| Fuente | Hallazgo |
|--------|----------|
| Hermes M5 (data MT5 real) | ~92.8% reclaim post-CHOCH |
| Experimento 2026-08-17 EURUSD Yahoo | M15 reclaim 77%; H1 81%; D1 confirm ~47% |
| Grid search excursion | k SCAN demasiado permisivo en LTF (precision ~24-29%) |

| TF | k SCAN (antes) | k CONFIRM (nuevo) | Precision orientativa |
|----|----------------|-------------------|----------------------|
| M15 | 2.0 | **4.0** | ~37% |
| H1 | 1.8 | **5.0** | ~61% |
| H4 | 1.5 | **3.0** | alta (n bajo) |
| D1 | 1.0 | **2.0** | ~70% |

Clases score: **premium ≥ 90** (antes 85), useful ≥ 70, noise < 70.

## 3. Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `tools/confirmation_thresholds.py` | **NUEVO** — single source of truth |
| `tools/choch_quality.py` | `choch_class_from_score` (90/70) |
| `tools/teacher_rubric.py` | klass vía mismos umbrales |
| `scripts/gen_choch_dataset.py` | K/FWD = modo CONFIRM + M15/H1 |
| `engine/bias_from_tools.py` | CHOCH solo **premium** mueve bias |
| `docs/UMBRALES_CONFIRMACION.md` | cuadro de calibración |
| `docs/motor_profesional_estado.md` | nota de calibración |

## 4. Política bias (importante)

Antes: cualquier CHOCH active (incluso noise) podía devolver BULLISH/BEARISH.  
Ahora: solo `choch_class == "premium"`. useful/noise = aviso, no dirección.

BOS active + bos_real sigue gobernando si no hay CHOCH premium.

## 5. Shadow / no promocionado

- No se tocó el modelo `data/learning/choch/full/model.joblib` (local, gitignored).
- Pipeline científico B4–B8 sigue pendiente de retomar.
- Re-generar dataset con nuevos K antes de re-entrenar nature head.

## 6. Cómo verificar

```bash
python -c "from tools.confirmation_thresholds import SCORE_PREMIUM, EXCURSION_K_CONFIRM; print(SCORE_PREMIUM, EXCURSION_K_CONFIRM)"
# smoke motor (requiere data/raw local):
# .venv/Scripts/python.exe -m scripts.smoke_motor_lectura
```

## 7. Siguiente acción

1. En PC con parquet MT5: regenerar `gen_choch_dataset` con K nuevos.  
2. Retomar pipeline B4 Nature Head.  
3. Comparar distribución premium/useful/noise vs teacher (~80% noise LTF esperado).
