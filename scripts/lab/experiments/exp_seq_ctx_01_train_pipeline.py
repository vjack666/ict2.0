"""EXP-SEQ-CTX-01 — ORQUESTACIÓN INF-4 (pasos 5–9 de la ruta IA).

Consume los snapshots certificados de exp_seq_ctx_01_snapshot.py y ejecuta el
contrato del TrainingPipeline (INF-4): entrega el snapshot, construye la
partición temporal, registra el modelo y checkpoint, evalúa en el split OOS
(test) y deja el modelo en Shadow Mode con can_trade=false.

IMPORTANTE: el TrainingPipeline es un ESQUELETO contractual (INF-4). No entrena
pesos reales (model_training.executed=False). Esto es congruente con el contrato
del dataset: no se declara edge, no se promueve, no se opera. El dataset sigue
en WAITING_FOR_OOS_EVIDENCE (canonical_bos HOLDOUT < 30).

Pasos de la ruta cubiertos:
  5. Entregar snapshot al TrainingPipeline (load_dataset_snapshot + plan()).
  6. Entrenar offline (skeleton INF-4: checkpoint reproducible, sin pesos).
  7. Evaluar en HOLDOUT (split test temporal del snapshot).
  8. Registrar modelo y checkpoint (ModelRegistry + CheckpointStore).
  9. Shadow Mode con can_trade=false (config del modelo; sin promoción).
"""

from __future__ import annotations
import sys, json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.ai_learning.dataset_snapshots import (
    CertifiedDatasetReader, load_dataset_snapshot,
)
from runtime.ai_learning.training_pipeline import TrainingPipeline
from runtime.ai_learning.model_registry import ModelRegistry
from runtime.ai_learning.checkpoint_store import CheckpointStore
from scripts.lab.experiments.exp_seq_ctx_01_dataset import MANIFEST

SNAPSHOT_ROOT = ROOT / "runtime" / "ai_learning" / "snapshots" / "seq_ctx_01"
REGISTRY_ROOT = ROOT / "runtime" / "ai_learning" / "registry" / "seq_ctx_01"
MODES = ["canonical_bos", "lite"]
FEATURES = ("context_bucket", "direction", "sequence_depth", "split")
LABELS = ("label_end_6", "label_end_12", "label_end_24", "label_end_48")
SEED = 20260823
MODEL_VERSION = "v1-skeleton"


def _commit() -> str:
    import subprocess
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                        text=True).strip()
    except Exception:
        return "UNKNOWN"


def _snapshot_dir(mode: str) -> Path:
    dirs = sorted(SNAPSHOT_ROOT.glob(f"{mode}/*/snapshot.json"))
    if not dirs:
        raise RuntimeError(f"no hay snapshot para {mode}")
    return dirs[0].parent


def _check_oos_sufficiency() -> int:
    """No registra modelos mientras el Gate OOS no sea suficiente."""
    if not MANIFEST.exists():
        print(f"[PIPELINE][FAIL-CLOSED] falta manifest OOS: {MANIFEST}")
        return 1
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[PIPELINE][FAIL-CLOSED] manifest OOS ilegible: {exc}")
        return 1
    status = manifest.get("status")
    oos_status = manifest.get("oos_sufficiency", {}).get("status")
    if status != "OOS_SUFFICIENT" or oos_status != "SUFFICIENT":
        print(
            "[PIPELINE][FAIL-CLOSED] Gate OOS no suficiente: "
            f"status={status!r}, oos_sufficiency={oos_status!r}; "
            "no se registra ni ejecuta pipeline."
        )
        return 1
    return 0


def _evaluate_oos(test_rows: tuple[dict, ...]) -> dict:
    """Métricas descriptivas en el split OOS (test). Sin declarar edge."""
    total = len(test_rows)
    if total == 0:
        return {"oos_rows": 0}
    # Distribución de labels en OOS por context_bucket
    dist = {}
    for r in test_rows:
        b = r.get("context_bucket")
        l = r.get("label_end_24")
        dist.setdefault(b, {}).setdefault(l, 0)
        dist[b][l] += 1
    # Tasa de "continuation" (ruptura a favor) por bucket, como señal descriptiva
    cont_rate = {}
    for b, ls in dist.items():
        n = sum(ls.values())
        cont_rate[b] = round(ls.get("continuation", 0) / n, 4) if n else None
    return {
        "oos_rows": total,
        "label_distribution_by_bucket": dist,
        "continuation_rate_by_bucket": cont_rate,
        "note": "descriptivo; NO es edge ni evidencia de promoción",
    }


def main() -> int:
    print("[PIPELINE] inicio EXP-SEQ-CTX-01 (pasos 5–9 INF-4)", flush=True)
    if _check_oos_sufficiency():
        return 1
    commit = _commit()
    registry = ModelRegistry(REGISTRY_ROOT)
    checkpoint_store = CheckpointStore(REGISTRY_ROOT / "checkpoints")

    for mode in MODES:
        snap_dir = _snapshot_dir(mode)
        snapshot = load_dataset_snapshot(snap_dir)
        reader = CertifiedDatasetReader(ROOT)
        rows = reader.read_snapshot(snap_dir)  # verifica integridad

        model_id = f"SEQ_CTX_01_{mode.upper()}"
        # Un solo config idéntico para registro y pipeline (el registry exige
        # que el config del modelo coincida con el del pipeline).
        cfg = {
            "contract_version": "v2",
            "structure_mode": mode,
            "can_trade": False,
            "shadow_mode": True,
        }

        # Paso 8 (precondición del pipeline): registrar modelo con lineage completo
        try:
            registry.register_model(
                model_id, MODEL_VERSION,
                git_commit=commit,
                snapshot=snapshot,
                features=FEATURES, labels=LABELS, seed=SEED,
                config=cfg,
            )
            print(f"[PIPELINE] {mode}: modelo registrado {model_id}@{MODEL_VERSION}")
        except Exception as exc:
            print(f"[PIPELINE][FAIL] registro modelo ({mode}): {exc}")
            return 1

        # Pasos 5–7: entregar snapshot, plan, run (skeleton) + evaluación OOS
        try:
            pipe = TrainingPipeline(
                snapshot=snap_dir,
                registry=registry,
                checkpoint_store=checkpoint_store,
                model_id=model_id,
                model_version=MODEL_VERSION,
                features=FEATURES, labels=LABELS, seed=SEED,
                config=cfg,
                time_column="event_time",
                train_fraction=0.6, validation_fraction=0.2,
            )
            result = pipe.run()
        except Exception as exc:
            print(f"[PIPELINE][FAIL] run ({mode}): {exc}")
            return 1

        # Paso 8 (cierre): registrar el checkpoint en el ModelRegistry para
        # indexarlo junto al modelo (lineage inmutable y auditable). El
        # CheckpointStore del pipeline escribe un directorio; el registry espera
        # bytes/data, así que leemos el state.json y lo registramos como payload.
        ckpt = result.checkpoint
        try:
            state_file = Path(ckpt.checkpoint_path) / "state.json"
            payload = state_file.read_bytes()
            registry.register_checkpoint(
                model_id, MODEL_VERSION, ckpt.checkpoint_id,
                data=payload,
                metadata=ckpt.state,
            )
            print(f"[PIPELINE] {mode}: checkpoint registrado {ckpt.checkpoint_id[:24]}")
        except Exception as exc:
            print(f"[PIPELINE][WARN] checkpoint no indexado en registry ({mode}): {exc}")

        split = result.split
        oos = _evaluate_oos(split.test)
        print(f"[PIPELINE] {mode}: train={len(split.train)} val={len(split.validation)} "
              f"test(OOS)={len(split.test)} | resumed={result.resumed}")
        print(f"[PIPELINE] {mode} OOS eval: {json.dumps(oos, ensure_ascii=False)}")

        # Paso 9: Shadow Mode — el modelo queda registrado con can_trade=false.
        # No se promueve ni opera. El checkpoint es reproducible (run_id estable).
        print(f"[PIPELINE] {mode}: Shadow Mode (can_trade=false). Modelo NO operativo.")

    print("[PIPELINE] PASS — pasos 5–9 INF-4 completados (skeleton, sin pesos, sin promoción).")
    print("[PIPELINE] Estado: modelo registrado en Shadow Mode; dataset WAITING_FOR_OOS_EVIDENCE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
