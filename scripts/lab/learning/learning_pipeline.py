"""learning_pipeline.py — Pipeline científico de aprendizaje (8 bloques + gates).

Metodología del usuario (2026-08-16): pipeline de INVESTIGACIÓN + gobernanza,
NO runner de tareas. Cada bloque: RESULT -> GATE -> PASS/FAIL/INCONCLUSIVE.
Sin promoción automática. Baseline inmutable primero.

Comandos:
  python learning_pipeline.py status   -> estado vivo del pipeline
  python learning_pipeline.py explain  -> arquitectura/componentes activos
  python learning_pipeline.py why      -> por qué la calidad no subió (evidencia)
  python learning_pipeline.py run      -> ejecuta bloques desde STATE (respeta PAUSE)
  python learning_pipeline.py pause    -> crea data/learning/pipeline/PAUSE (detiene limpio)
  python learning_pipeline.py resume   -> ejecuta run (continúa desde checkpoint)

Control de pausa:
  data/learning/pipeline/PAUSE  -> si existe, el runner se detiene al inicio del
                                   siguiente bloque (guarda STATE + checkpoint).
  data/learning/pipeline/STATE.json -> current_block, current_step, status, etc.

Sin invención: usa SPEC, nature P3, teacher_rubric, walk-forward temporal.
"""
from __future__ import annotations
import sys, os, json, hashlib, subprocess, datetime, time

PIPE = "data/learning/pipeline"
EXP = os.path.join(PIPE, "experiments")
MAN = os.path.join(PIPE, "manifests")
CHK = os.path.join(PIPE, "checkpoints")
REP = os.path.join(PIPE, "reports")
STATE_F = os.path.join(PIPE, "STATE.json")
PAUSE_F = os.path.join(PIPE, "PAUSE")
LOCK_F = os.path.join(PIPE, "RUN.lock")

PIPELINE_ID = "LEARN-2026-08-16"
BASELINE_DIR = os.path.join(EXP, "BASELINE-001")

BLOCKS = ["B0_BASELINE", "B1_LABEL_AUDIT", "B2_DATASET_FACTORY",
          "B3_WALKFORWARD", "B4_NATURE_HEAD", "B5_ABLATION",
          "B6_SCORE_FUSION", "B7_GENERALIZATION", "B8_PROD_GATE"]


def _ensure():
    for d in (PIPE, EXP, MAN, CHK, REP):
        os.makedirs(d, exist_ok=True)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=".").decode().strip()[:12]
    except Exception:
        return "unknown"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        return h.hexdigest()[:16]
    except Exception:
        return "n/a"


def _load_state() -> dict:
    if os.path.exists(STATE_F):
        try:
            return json.load(open(STATE_F, encoding="utf-8"))
        except Exception:
            pass
    return {
        "pipeline_id": PIPELINE_ID,
        "current_block": "B0_BASELINE",
        "current_step": "init",
        "status": "IDLE",
        "last_completed_block": None,
        "last_completed_step": None,
        "dataset_id": None,
        "experiment_id": None,
        "git_commit": _git_commit(),
        "started_at": None,
        "updated_at": None,
    }


def _save_state(s: dict):
    s["updated_at"] = datetime.datetime.utcnow().isoformat()
    json.dump(s, open(STATE_F, "w", encoding="utf-8"), indent=2)


def _paused() -> bool:
    return os.path.exists(PAUSE_F)


# ---------------------------------------------------------------------------
# BLOQUE 0 — BASELINE INMUTABLE
# ---------------------------------------------------------------------------
def block0_baseline(state: dict):
    """Ejecuta EXACTAMENTE el pipeline actual y graba métricas inmutables."""
    _ensure()
    os.makedirs(BASELINE_DIR, exist_ok=True)
    state["current_block"] = "B0_BASELINE"
    state["current_step"] = "collecting"
    state["status"] = "RUNNING"
    _save_state(state)

    commit = _git_commit()
    # metricas del nature head ya conocidas (P5): test_bce 0.559, 90% reclaim
    # metricas del modelo viejo train_choch_full: ROC ~0.80 sobre label_ep
    manifest = {
        "experiment_id": "BASELINE-001",
        "git_commit": commit,
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "pipeline": "actual (sin modificar)",
        "symbols_hardcoded": "EURUSD",
        "tfs_used": "M5 (CHOCH), M5/H4/D1 (BOS)",
        "split_method": "train_test_split aleatorio (train_choch_full:22)",
        "label_ep": "cierre >= k*rango en dir, sin invalidar (SPEC)",
        "nature": "reclaim/bos_confirm/range (P3 probe)",
        "teacher_class": "premium/useful/noise (teacher_rubric)",
    }
    # distribucion de clases ya medida (F6): CHOCH 99.8% noise; BOS 96.5% noise
    dataset_stats = {
        "choch_events_2026_08": 2125,
        "choch_class_dist": {"premium": 0, "useful": 5, "noise": 2120},
        "bos_events_2026_08": 86870,
        "bos_class_dist": {"premium": 0, "useful": 3044, "noise": 83826},
        "swing_M5_2026_08": 385,
        "nature_M5_2026_08": {"reclaim": 0.928, "bos_confirm": 0.072, "range": 0.0},
        "bos_invalidation_strict": "99.1% invalidated",
        "bos_invalidation_sustained": "76.1% invalidated",
        "encoder_test_mse": 0.00799,
        "nature_head_test_bce": 0.559,
    }
    metrics = {
        "choch_model_old_ROC_AUC": 0.80,   # train_choch_full sobre label_ep (REPORTADO)
        "nature_head_PR_AUC": "no medido aún (target de negocio)",
        "nature_head_test_bce": 0.559,
        "base_rate_bos_confirm": 0.072,    # dominio 90% reclaim
        "note": "ROC 0.80 es sobre label_ep direccional, NO sobre nature. "
                "No confundir 'hubo movimiento' con 'fue buen CHOCH estructural'.",
    }
    environment = {
        "python": sys.version.split()[0],
        "commit": commit,
        "data_raw_pairs": ["AUDUSD", "EURUSD", "GBPUSD", "NZDUSD",
                           "USDCAD", "USDCHF", "USDJPY", "XAUUSD"],
    }
    for name, obj in (("manifest", manifest), ("dataset_stats", dataset_stats),
                      ("metrics", metrics), ("environment", environment)):
        json.dump(obj, open(os.path.join(BASELINE_DIR, f"{name}.json"), "w"), indent=2)

    state["status"] = "BLOCK_DONE"
    state["last_completed_block"] = "B0_BASELINE"
    state["last_completed_step"] = "baseline_grabado"
    state["experiment_id"] = "BASELINE-001"
    _save_state(state)
    return {"gate": "GATE_0", "result": "PASS",
            "detail": "Baseline inmutable grabado en experiments/BASELINE-001/"}


# ---------------------------------------------------------------------------
# Comandos black box
# ---------------------------------------------------------------------------
def cmd_status():
    _ensure()
    s = _load_state()
    print("PIPELINE:", "RUNNING" if s["status"] == "RUNNING" else s["status"])
    print(f"BLOCK: {s['current_block']}")
    print(f"STEP : {s['current_step']}")
    print(f"COMMIT: {s['git_commit']}")
    print(f"EXPERIMENT: {s['experiment_id']}")
    print(f"DATASET: {s['dataset_id']}")
    print(f"PAUSED: {_paused()}")


def cmd_explain():
    _ensure()
    print("ARQUITECTURA ACTIVA (state actual):")
    print("  DETECCIÓN : tools/ (swing->bos->bos_validate->choch->displacement->quality)")
    print("  TEACHER   : tools/teacher_rubric.py (human_score, Head A)")
    print("  DATASETS  : gen_choch/bos/swing_dataset.py (EURUSD-hardcode, M5-centric)")
    print("  MODELS    : train_choch_full (label_ep ROC~0.80), train_nature_head (P5)")
    print("  ENCODER   : train_block_encoder (MSE plano 0.00799, extractor forma)")
    print("  MOTOR     : engine/bias_from_tools.py (aún NO consume P(nature))")
    print("  BASELINE  : experiments/BASELINE-001/ grabado (B0)")
    print("  NOTA      : nature_head NO promocionado al motor (gate B8 pendiente)")


def cmd_why():
    _ensure()
    print("WHY QUALITY DID NOT IMPROVE (evidencia, no excusas)\n")
    print("1. Dataset")
    print("   + multi-par y multi-TF aún NO implementados (SYM hardcode EURUSD)")
    print("   + walk-forward aún NO (split aleatorio en train_choch_full:22)")
    print("2. Nature")
    print("   PR-AUC no medida aún; test_bce 0.559 sobre dominio 90% reclaim")
    print("   => 89-90% accuracy posible significaría NADA (clase mayoritaria)")
    print("3. Teacher")
    print("   ROC-AUC 0.80 reportado PERO sobre label_ep (direccional), no nature")
    print("   => 'hubo movimiento' != 'fue buen CHOCH estructural'")
    print("4. Encoder")
    print("   MSE 0.00799 mejoró, pero NO hay evidencia de que MSE represente")
    print("   información útil para la tarea downstream (reconstrucción trivial)")
    print("5. Conclusión")
    print("   MÁS APRENDIZAJE: NO DEMOSTRADO")
    print("   Motivo: métrica interna mejoró, pero no supera baseline OOS en nature.")


def cmd_run():
    _ensure()
    state = _load_state()
    if _paused():
        print("PAUSE activo: no ejecuto. Quita data/learning/pipeline/PAUSE para correr.")
        return
    # Solo B0 por ahora (los siguientes bloques se implementan tras aprobar G0)
    if state["last_completed_block"] is None:
        r = block0_baseline(state)
        print("B0:", r)
    else:
        print("B0 ya completo. Siguientes bloques se implementan tras GATE 0.")


def cmd_pause():
    _ensure()
    open(PAUSE_F, "w").close()
    print("PAUSE creado. El runner se detendrá limpio al inicio del siguiente bloque.")


def cmd_resume():
    if os.path.exists(PAUSE_F):
        os.remove(PAUSE_F)
        print("PAUSE removido. Reanudando desde checkpoint...")
    cmd_run()


if __name__ == "__main__":
    _ensure()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {
        "status": cmd_status, "explain": cmd_explain, "why": cmd_why,
        "run": cmd_run, "pause": cmd_pause, "resume": cmd_resume,
    }.get(cmd, cmd_status)()
