"""CHOCH de calidad (EXP-012) — rescate aislado de SMC-SYSTEMS.

Fuente: SMC-SYSTEMS/engine/bos/structure.py::_exp012_choch_marks.
Adaptado a tools/ (aislado, usa SwingTool + BOSTool).

Marca CHOCH REALES (bonus de autoridad) aplicando las 4 reglas de la tesis:
  (a) MOMENTUM: racha >=2 HH (uptrend) para CHOCH bajista, o >=2 LL
      (downtrend) para CHOCH alcista. Sin empuje no hay "caracter" que
      cambiar -> es ruido.
  (b) AFTER_BOS REAL: hubo un BOS de mercado confirmado en la direccion
      OPUESTA al CHOCH (el BOS que el CHOCH viene a revertir).
  (c) NIVEL = ULTIMO HL (CHOCH bajista) / LH (alcista) ROTO, NO el nivel
      del BOS roto. Son pivotes distintos; usar el BOS dispara CHOCH
      prematuro y deja ruido.
  (d) RECLAIM: status == invalidated invalida el CHOCH.

Score hibrido (plan v1.1 F2):
  Estructura 30 + Contexto HTF 20 + Geometria 20 + Confirmacion 15 + IA 15.

COMPONENTE IA (15%):
  Un modelo (RandomForest/GradientBoosting) entrenado sobre TODA la data
  historica predice P(label=1) donde label = "el precio siguió en la
  dirección del giro >= k*rango promedio sin invalidarse". Ese probabilidad
  rellena el 15% reservado (score += 15 * P). El modelo se carga una vez
  (cache) desde data/learning/choch/*/model.joblib. Si no existe o ROC<0.55
  (decisión de entrenamiento), el 15% queda en 0 y el score es puramente
  geométrico.

CORRECCION HTF (2026-08-16):
  detect_trend() devuelve un DataFrame con columna 'trend'/'trend_int' por
  barra. El código previo hacía isinstance(df, dict) -> False -> htf_ctx
  siempre 'neutral' (feature muerta). Ahora se calcula el sesgo HTF por barra
  via merge_asof (prioridad D1 > H4 > H1) y se usa de verdad.

PERF (2026-08-16):
  predict_proba de sklearn cuesta ~65ms por fila en entradas tiny => se
  BATCHEA: se recolectan todas las filas y se predice UNA vez al final.
"""
from __future__ import annotations

import os
import glob
import numpy as np
import pandas as pd

from tools.event import ToolEvent


# Orden canónico de features usado TANTO en entrenamiento como en runtime.
# score_n = choch_score/100 ; htf_ctx_code: contra=0/neutral=1/a_favor=2 ;
# cd = dirección del giro (+1/-1) ; tf_code: M5=0/H4=1/D1=2.
FEATURES = [
    "score_n", "momentum", "after_bos", "displacement", "htf_ctx_code",
    "htf_trend_int", "cd", "break_body_ratio", "dist_to_level",
    "bos_age_bars", "tf_code",
]

_MODEL_CACHE = {"model": None, "features": None, "path": None, "tried": False}


def _find_model() -> str | None:
    """Busca el model.joblib más reciente bajo data/learning/choch/."""
    base = os.path.join("data", "learning", "choch")
    if not os.path.isdir(base):
        return None
    cands = []
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f == "model.joblib":
                cands.append(os.path.join(root, f))
    if not cands:
        return None
    cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return cands[0]


def _load_model():
    """Carga (una vez) el modelo IA. Devuelve (model, features) o (None, None).

    Si CHOCH_IA_DISABLE=1 (lo fija scripts/gen_choch_dataset.py), se omite:
    la generacion de dataset debe usar SIEMPRE el score geometrico para que las
    features de entrenamiento sean estables y no se contamine con el propio modelo.
    """
    if os.environ.get("CHOCH_IA_DISABLE"):
        return None, None
    if _MODEL_CACHE["tried"]:
        return _MODEL_CACHE["model"], _MODEL_CACHE["features"]
    _MODEL_CACHE["tried"] = True
    p = _find_model()
    if p is None:
        return None, None
    try:
        import joblib
        obj = joblib.load(p)
        if isinstance(obj, dict) and "model" in obj:
            _MODEL_CACHE["model"] = obj["model"]
            _MODEL_CACHE["features"] = obj.get("features", FEATURES)
        else:
            _MODEL_CACHE["model"] = obj
            _MODEL_CACHE["features"] = FEATURES
        _MODEL_CACHE["path"] = p
        return _MODEL_CACHE["model"], _MODEL_CACHE["features"]
    except Exception as e:  # pragma: no cover
        print(f"[choch_quality] modelo no cargable ({e}); score geometrico.")
        return None, None


def _htf_bias_array(htf_frames, times: pd.Series) -> np.ndarray:
    """Sesgo HTF por barra (int -1/0/1) via merge_asof, prioridad D1>H4>H1.

    htf_frames: dict {tf: DataFrame | dict}. Los DataFrame deben tener
    'time' y 'trend_int' (o 'trend'). Un dict se trata como sesgo constante.
    """
    if not htf_frames:
        return np.zeros(len(times), dtype=float)

    def _norm(ts):
        ts = pd.to_datetime(ts)
        if getattr(ts.dt, "tz", None) is not None:
            ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
        return ts.astype("datetime64[ns]")

    tvals = _norm(times).reset_index(drop=True)
    priority = [t for t in ("D1", "H4", "H1", "M15", "M5") if t in htf_frames]
    if not priority:
        return np.zeros(len(times), dtype=float)

    biases = {}
    for tf in priority:
        hf = htf_frames[tf]
        if isinstance(hf, pd.DataFrame):
            hf2 = hf.copy()
            hf2["_t"] = _norm(hf2["time"])
            if "trend_int" in hf2.columns:
                ti = pd.to_numeric(hf2["trend_int"], errors="coerce").fillna(0.0)
            elif "trend" in hf2.columns:
                ti = hf2["trend"].map(
                    {"BULLISH": 1, "BEARISH": -1, "RANGING": 0}
                ).fillna(0.0).astype(float)
            else:
                continue
            right = pd.DataFrame({"_t": hf2["_t"].values, "ti": ti.values})
            right = right.sort_values("_t")
            merged = pd.merge_asof(
                pd.DataFrame({"_t": tvals}).sort_values("_t"),
                right, on="_t", direction="backward",
            )
            biases[tf] = merged["ti"].fillna(0.0).to_numpy()
        elif isinstance(hf, dict):
            b = 0
            if "trend_int" in hf:
                b = int(hf["trend_int"])
            elif "trend" in hf:
                b = {"BULLISH": 1, "BEARISH": -1, "RANGING": 0}.get(str(hf["trend"]).upper(), 0)
            biases[tf] = np.full(len(times), float(b))

    arr = np.zeros(len(times), dtype=float)
    for tf in priority:
        if tf in biases:
            b = biases[tf]
            arr = np.where(arr == 0, b, arr)
    return arr


def mark_choch_quality(
    df: pd.DataFrame,
    choch_events: list[ToolEvent],
    swing_events: list[ToolEvent],
    bos_events: list[ToolEvent],
    htf_frames: dict | None = None,
) -> list[ToolEvent]:
    """Anota cada CHOCH con extra['choch_real'] y extra['choch_score'] (0-100).

    Usa swings (HH/HL/LH/LL) y BOS (dir, real) de las herramientas de tools/.
    Score hibrido (plan v1.1 F2):
      Estructura 30 + Contexto HTF 20 + Geometria 20 + Confirmacion 15 + IA 15.
    """
    n = len(df)
    if n == 0:
        return choch_events

    close = df["close"].to_numpy() if "close" in df.columns else np.array([])
    open_ = df["open"].to_numpy() if "open" in df.columns else np.array([])
    high = df["high"].to_numpy() if "high" in df.columns else np.array([])
    low = df["low"].to_numpy() if "low" in df.columns else np.array([])
    avg_range = (df["high"] - df["low"]).clip(lower=0.0).rolling(14, min_periods=1).mean().to_numpy() \
        if "high" in df.columns else np.zeros(n)

    # Sesgo HTF por barra (corrige bug de htf_ctx siempre neutral)
    htf_bias_at = _htf_bias_array(htf_frames, df["time"]) if "time" in df.columns else np.zeros(n)

    bos_dir_by_bar = {}
    for b in bos_events:
        bb = b.break_bar if b.break_bar is not None else b.bar_index
        if bb is None:
            continue
        d = 1 if b.signal == "BOS_UP" else -1
        bos_dir_by_bar[bb] = d

    swings_sorted = sorted(
        [s for s in swing_events if s.origin_bar is not None],
        key=lambda e: e.origin_bar,
    )
    lab_by_bar = {}
    for s in swings_sorted:
        sig = s.signal
        lab = {"SWING_HH": "HH", "SWING_HL": "HL", "SWING_LH": "LH", "SWING_LL": "LL"}.get(sig, "NONE")
        lab_by_bar[s.origin_bar] = (lab, s.price)

    last_bos_dir_at = {i: 0 for i in range(n)}
    last_bos_bar_at = {i: -999999 for i in range(n)}
    cur_dir = 0
    cur_bar = -999999
    for i in range(n):
        if i in bos_dir_by_bar:
            cur_dir = bos_dir_by_bar[i]
            cur_bar = i
        last_bos_dir_at[i] = cur_dir
        last_bos_bar_at[i] = cur_bar

    choch_sorted = sorted(
        [c for c in choch_events if c.break_bar is not None],
        key=lambda e: e.break_bar,
    )
    hh_streak = ll_streak = 0
    last_hl = last_lh = np.nan
    choch_by_bar = {c.break_bar: c for c in choch_sorted}

    bars = sorted(lab_by_bar.keys())
    bi = 0
    model, model_features = _load_model()

    # acumuladores para prediccion BAATCH (evita N llamadas costosas a predict)
    items = []      # (c, base_score)
    feat_rows = []  # filas en orden FEATURES (score_n = base_score/100)

    for i in range(n):
        while bi < len(bars) and bars[bi] <= i:
            lab, price = lab_by_bar[bars[bi]]
            if lab == "HH":
                hh_streak += 1
                ll_streak = 0
                last_hl = np.nan
            elif lab == "LL":
                ll_streak += 1
                hh_streak = 0
                last_lh = np.nan
            elif lab == "HL":
                last_hl = price
                ll_streak = 0
            elif lab == "LH":
                last_lh = price
                hh_streak = 0
            bi += 1

        if i not in choch_by_bar:
            continue
        c = choch_by_bar[i]
        cd = 1 if c.signal == "CHOCH_UP" else -1
        if cd == -1:
            momentum_ok = hh_streak >= 2
            lvl = last_hl
        else:
            momentum_ok = ll_streak >= 2
            lvl = last_lh
        bos_prev_dir = last_bos_dir_at[i]
        after_bos = (bos_prev_dir == -cd)
        disp_now = bool(df["displacement_bullish"].iloc[i]) if cd == 1 else bool(df["displacement_bearish"].iloc[i])
        disp_conf = False
        for j in range(i + 1, min(i + 3, len(df))):
            if cd == 1 and bool(df["displacement_bullish"].iloc[j]):
                disp_conf = True
                break
            if cd == -1 and bool(df["displacement_bearish"].iloc[j]):
                disp_conf = True
                break
        disp = disp_now or disp_conf
        lvl_present = pd.notna(lvl)
        is_real = bool(after_bos and lvl_present)

        lvl_f = float(lvl) if lvl_present else np.nan
        if n > 0 and i < len(open_) and (high[i] - low[i]) > 1e-12:
            body_r = abs(close[i] - open_[i]) / (high[i] - low[i])
        else:
            body_r = 0.0
        if lvl_present and avg_range[i] > 1e-9:
            dist_lvl = abs(close[i] - lvl_f) / avg_range[i]
        else:
            dist_lvl = 0.0
        bos_age = (i - last_bos_bar_at[i]) if last_bos_bar_at[i] >= 0 else -1
        htf_bias = int(htf_bias_at[i]) if i < len(htf_bias_at) else 0
        if htf_bias == cd:
            htf_ctx = "a_favor"
        elif htf_bias == -cd and htf_bias != 0:
            htf_ctx = "contra"
        else:
            htf_ctx = "neutral"
        htf_ctx_code = {"contra": 0, "neutral": 1, "a_favor": 2}[htf_ctx]
        tf_code = {"M5": 0, "H4": 1, "D1": 2}.get(str(c.tf).upper(), 0)

        # --- SCORE HIBRIDO (GEOMETRICO) sin IA todavia ---
        base = 0.0
        if is_real:
            base += 70.0
            if momentum_ok:
                base += 10.0
        if htf_ctx == "a_favor":
            base += 20.0
        elif htf_ctx == "contra":
            base += 5.0
        else:
            base += 10.0
        if disp:
            base += 20.0
        if c.status != "invalidated":
            base += 15.0
        base = float(np.clip(base, 0.0, 100.0))

        # extras (no dependen de IA, se fijan ya)
        c.extra["choch_real"] = is_real
        c.extra["choch_pivot_level"] = float(lvl_f) if lvl_present else None
        c.extra["choch_momentum"] = bool(momentum_ok)
        c.extra["choch_after_bos"] = bool(after_bos)
        c.extra["choch_displacement"] = disp
        c.extra["choch_htf_ctx"] = htf_ctx
        c.extra["choch_htf_trend_int"] = htf_bias
        c.extra["choch_cd"] = cd
        c.extra["choch_break_body_ratio"] = float(body_r)
        c.extra["choch_dist_to_level"] = float(dist_lvl)
        c.extra["choch_bos_age_bars"] = int(bos_age) if bos_age >= 0 else None

        items.append((c, base))
        feat_rows.append([
            base / 100.0,
            1.0 if momentum_ok else 0.0,
            1.0 if after_bos else 0.0,
            1.0 if disp else 0.0,
            float(htf_ctx_code),
            float(htf_bias),
            float(cd),
            float(body_r),
            float(dist_lvl),
            float(bos_age) if bos_age >= 0 else 0.0,
            float(tf_code),
        ])

    # --- COMPONENTE IA: una sola llamada batch ---
    ia_probs = [0.0] * len(items)
    if model is not None and feat_rows:
        try:
            feats = model_features if model_features else FEATURES
            col_map = {name: k for k, name in enumerate(FEATURES)}
            X = np.array([[row[col_map[f]] for f in feats] for row in feat_rows], dtype=float)
            ia_probs = model.predict_proba(X)[:, 1].tolist()
        except Exception:
            ia_probs = [0.0] * len(items)

    for (c, base), p in zip(items, ia_probs):
        final = float(np.clip(base + 15.0 * p, 0.0, 100.0))
        c.extra["choch_ia_prob"] = float(p)
        c.extra["choch_score"] = final
        if final >= 85:
            c.extra["choch_class"] = "premium"
        elif final >= 70:
            c.extra["choch_class"] = "useful"
        else:
            c.extra["choch_class"] = "noise"

    return choch_events
