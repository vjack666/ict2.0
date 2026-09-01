# Bitácora — Cierre calibración IA score CHOCH (toda la data)

**Fecha:** 2026-08-16 00:30 UTC-5
**Pedido:** calibrar por IA el score CHOCH con TODA la data, entregar perfecto.

---

## Hallazgo: agente delegado truncó (rate-limit API)
Se delegó a subagente; truncó por rate-limit ANTES de entrenar/validar.
Dejó `model.joblib` = **dict inválido** (no clasificador) y datasets por mes
como eventos crudos SIN label. La integración en `choch_quality.py` cargaba
ese dict, fallaba, y caía a score geométrico (fallback). La IA NO estaba
realmente activa. Aplicada regla de oro: no afirmar "perfecto" sin evidencia.

## Recuperación (autónoma, sin agente)
1. `gen_choch_dataset.py` mejorado a TODA la data (M5 334k + H4 + D1) con
   labels label_ep/peak/dir. Regenerado: **2125 CHOCH REAL** (M5=2037, H4=83, D1=5).
2. `train_choch_full.py`: entrena RF/GBM/LR con holdout estratificado.
   - label_ep (precio cerró a favor + no invalidado): **ROC-AUC 0.798** (GBM)
   - label_peak: 0.790 | label_dir: 0.594
3. Modelo GUARDADO en data/learning/choch/full/model.joblib
   (dict {model, features, label, roc_auc}); formato que _load_model espera.
4. Smoke test motor: choch_ia_prob rango 0.001-0.909, mean 0.12, 2193/6540
   CHOCH con prob>0. IA ACTIVA de verdad. Bias M5 = BULLISH (noise).

## Resumen de archivos
- scripts/gen_choch_dataset.py: TODA la data + 3 labels (modificado)
- scripts/train_choch_full.py: entrena y guarda modelo válido (nuevo)
- scripts/eval_model_small.py / eval_choch_model.py: eval ROC (nuevos)
- tools/choch_quality.py: integración IA (predict_proba batch + 15*P)
- engine/bias_from_tools.py: bias_from_tools_htf (sesgo HTF con tools)
- engine/htf_narrative.py: cableo use_tools=True (motor usa tools)
- engine/bias/narrative.py: limpieza warnings Pylance (motor viejo en uso)

## Veredicto
EDGE REAL confirmado por ROC 0.798 (no es NO-EDGE). La IA calibrada con
toda la data EURUSD disponible está integrada y activa en el score híbrido.
No se commitea data/ (gitignore); solo scripts + código.
