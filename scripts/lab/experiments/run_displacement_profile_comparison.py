"""Ejecuta una comparación finita BASELINE/ICT_ONLY y deja estado legible.

LOCAL_ONLY y DIAGNOSTIC_ONLY. No reintenta, no ejecuta órdenes y termina al
completar exactamente los dos ajustes solicitados.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.ai_learning.diagnostic_training import (
    DiagnosticTrainingError,
    run_diagnostic_training,
    write_diagnostic_artifact,
)
from runtime.ai_learning.outcome_classifier import FEATURE_NAMES, INTRADAY_FEATURE_PROFILES


PROFILES = {"BASELINE": FEATURE_NAMES, "ICT_ONLY": INTRADAY_FEATURE_PROFILES["ICT_ONLY"]}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_status(path: Path, **state: object) -> None:
    body = {"updated_at": _now(), "can_trade": False, "mode": "DIAGNOSTIC_ONLY", **state}
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--target", default="label_end_6")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        # Start-Process necesita crear los logs antes de arrancar el runner.
        # Se acepta exclusivamente un directorio que contiene logs vacíos; todo
        # artefacto de entrenamiento previo sigue siendo inmutable.
        unexpected = [path.name for path in output_dir.iterdir() if path.suffix != ".log"]
        if unexpected:
            raise SystemExit(f"output-dir contiene artefactos y no se sobrescribe: {output_dir}")
    else:
        output_dir.mkdir(parents=True)
    status = output_dir / "status.json"
    results: dict[str, dict] = {}
    _write_status(status, state="RUNNING", current_step="BASELINE", completed_profiles=[], total_profiles=2)
    try:
        for profile, names in PROFILES.items():
            _write_status(status, state="RUNNING", current_step=profile, completed_profiles=list(results), total_profiles=2)
            payload = run_diagnostic_training(
                args.jsonl, target=args.target, seed=args.seed, iterations=args.iterations,
                learning_rate=args.learning_rate, feature_names=names,
            )
            payload["requested_feature_profile"] = profile
            artifact = write_diagnostic_artifact(payload, output_dir / f"{profile.lower()}.json")
            results[profile] = {
                "artifact": str(artifact),
                "status": payload["status"],
                "fit_executed": payload["fit_executed"],
                "test_oos": payload.get("metrics", {}).get("test_oos"),
                "feature_names": payload.get("model", {}).get("feature_names", []),
            }
        baseline = results["BASELINE"]["test_oos"] or {}
        ict = results["ICT_ONLY"]["test_oos"] or {}
        summary = {
            "kind": "DISPLACEMENT_PROFILE_COMPARISON",
            "input": str(args.jsonl.resolve()),
            "target": args.target,
            "seed": args.seed,
            "iterations": args.iterations,
            "can_trade": False,
            "diagnostic_only": True,
            "results": results,
            "oos_accuracy_delta_ict_minus_baseline": (
                float(ict.get("accuracy", 0.0)) - float(baseline.get("accuracy", 0.0))
            ),
        }
        (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_status(status, state="FINALIZADO", current_step=None, completed_profiles=list(results), total_profiles=2, summary=str(output_dir / "summary.json"))
    except (DiagnosticTrainingError, OSError, ValueError) as exc:
        _write_status(status, state="FAILED", current_step=None, completed_profiles=list(results), total_profiles=2, error=str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
