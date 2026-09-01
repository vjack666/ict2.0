"""Optimización diagnóstica acotada para la línea intradía Wyckoff + ICT.

Selecciona un candidato usando únicamente TRAIN/VALIDATION. TEST/OOS se
conserva como diagnóstico y el HOLDOUT 2021–2025 no se lee.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.ai_learning.diagnostic_training import (
    load_causal_jsonl,
    run_diagnostic_training,
    write_diagnostic_artifact,
)
from runtime.ai_learning.outcome_classifier import INTRADAY_FEATURE_PROFILES


DEFAULT_INPUT = ROOT / "reports" / "audits" / "experiments" / "ai" / "wyckoff_intraday_2006_2010.jsonl"
DEFAULT_OUTPUT = ROOT / "reports" / "audits" / "experiments" / "ai" / "wyckoff_intraday_2006_2010_optimization"
TARGET = "label_end_12"
SEED = 20260831
LEARNING_RATES = (0.02, 0.05)
L2_VALUES = (1e-4, 1e-3)
ITERATIONS = 500
VARIANTS = (
    ("ICT_ONLY", "ict_only"),
    ("WYCKOFF_ONLY", "wyckoff_only"),
    ("WYCKOFF_ICT_COMBINED", "wyckoff_ict_combined"),
)


def candidate_grid() -> Iterable[dict[str, Any]]:
    """Devuelve la rejilla congelada en orden estable."""
    for profile, _slug in VARIANTS:
        for learning_rate in LEARNING_RATES:
            for l2 in L2_VALUES:
                yield {
                    "profile": profile,
                    "learning_rate": learning_rate,
                    "l2": l2,
                    "iterations": ITERATIONS,
                    "seed": SEED,
                }


def selection_key(candidate: dict[str, Any]) -> tuple[float, float, int, float, float]:
    """Criterio cerrado; no accede a métricas TEST/OOS."""
    validation = candidate["metrics"]["validation"]
    profile_order = {name: index for index, (name, _slug) in enumerate(VARIANTS)}
    return (
        float(validation["log_loss"]),
        -float(validation["accuracy"]),
        profile_order[candidate["profile"]],
        float(candidate["learning_rate"]),
        float(candidate["l2"]),
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"salida ya existe y no se sobrescribe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_new_text(path: Path, content: str) -> None:
    if path.exists():
        raise SystemExit(f"salida ya existe y no se sobrescribe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Optimización diagnóstica intradía Wyckoff + ICT",
        "",
        f"- **Estado:** `{report['status']}`",
        f"- **Criterio:** menor `validation.log_loss`; empates por accuracy",
        f"- **Candidatos:** {report['candidate_count']}",
        f"- **Corpus SHA-256:** `{report['input']['sha256']}`",
        "- **TEST/OOS:** solo diagnóstico; no selección",
        "- **HOLDOUT 2021–2025:** no leído",
        "",
        "| # | Perfil | lr | l2 | Val accuracy | Val log-loss | Test/OOS accuracy | Seleccionado |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for index, candidate in enumerate(report["candidates"], start=1):
        validation = candidate["metrics"]["validation"]
        test = candidate["metrics"]["test_oos"]
        selected = "SÍ" if candidate["candidate_id"] == report["selected_candidate_id"] else ""
        lines.append(
            f"| {index} | {candidate['profile']} | {candidate['learning_rate']:.4f} | "
            f"{candidate['l2']:.4f} | {validation['accuracy']:.6f} | "
            f"{validation['log_loss']:.6f} | {test['accuracy']:.6f} | {selected} |"
        )
    lines.extend([
        "",
        "## Dictamen",
        "",
        "El ganador se seleccionó sin leer TEST/OOS ni HOLDOUT. Este resultado",
        "sigue siendo diagnóstico y no demuestra edge, rentabilidad ni autoriza",
        "`TRAINING_ELIGIBLE`, MT5 u órdenes.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source = args.input.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"directorio no vacío; no se sobrescribe: {output_dir}")

    rows = load_causal_jsonl(source, target=TARGET)
    code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    candidates: list[dict[str, Any]] = []
    for index, config in enumerate(candidate_grid(), start=1):
        diagnostic = run_diagnostic_training(
            source,
            target=TARGET,
            seed=SEED,
            iterations=ITERATIONS,
            learning_rate=config["learning_rate"],
            l2=config["l2"],
            code_commit=code_commit,
            feature_names=INTRADAY_FEATURE_PROFILES[config["profile"]],
        )
        artifact_path = output_dir / f"candidate_{index:02d}_{config['profile'].lower()}_lr{config['learning_rate']}_l2{config['l2']}.json"
        write_diagnostic_artifact(diagnostic, artifact_path)
        candidates.append({
            "candidate_id": f"C{index:02d}",
            **config,
            "artifact": str(artifact_path),
            "artifact_file_sha256": _file_sha256(artifact_path),
            "artifact_hash": diagnostic["artifact_hash"],
            "status": diagnostic["status"],
            "fit_executed": diagnostic["fit_executed"],
            "can_trade": diagnostic["can_trade"],
            "metrics": diagnostic["metrics"],
            "temporal_split": diagnostic["temporal_split"],
            "input": diagnostic["input"],
            "source_code_commit": diagnostic["model"]["source_code_commit"],
        })

    selected = min(candidates, key=selection_key)
    input_hashes = {candidate["input"]["sha256"] for candidate in candidates}
    split_shapes = {json.dumps(candidate["temporal_split"], sort_keys=True) for candidate in candidates}
    if input_hashes != {rows.raw_sha256} or len(split_shapes) != 1:
        raise SystemExit("candidatos no comparten input hash o split temporal")
    if any(candidate["status"] != "DIAGNOSTIC_ONLY_COMPLETED" for candidate in candidates):
        raise SystemExit("un candidato no terminó en DIAGNOSTIC_ONLY_COMPLETED")
    if any(candidate["source_code_commit"] != code_commit for candidate in candidates):
        raise SystemExit("un candidato no referencia el commit actual")

    report = {
        "schema_version": "1.0",
        "status": "DIAGNOSTIC_OPTIMIZATION_COMPLETED",
        "mode": "DIAGNOSTIC_ONLY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_commit": code_commit,
        "target": TARGET,
        "selection_scope": "TRAIN fit + VALIDATION selection only",
        "selection_metric": "validation.log_loss ascending; validation.accuracy descending on tie",
        "test_oos_used_for_selection": False,
        "holdout_2021_2025_used": False,
        "can_trade": False,
        "shadow_mode": True,
        "scientific_training_eligible": False,
        "candidate_count": len(candidates),
        "input": {
            "path": str(source),
            "rows": len(rows.rows),
            "sha256": rows.raw_sha256,
            "schema_hash": rows.schema_hash,
        },
        "candidates": candidates,
        "selected_candidate_id": selected["candidate_id"],
        "selected_candidate": selected,
        "next_action": "Congelar el candidato y ejecutar evaluación HOLDOUT 2021-2025 sin reajuste; luego calibración, abstención y drift.",
    }
    report["report_hash"] = hashlib.sha256(
        json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    report_path = output_dir / "optimization.json"
    markdown_path = output_dir / "optimization.md"
    _write_new_json(report_path, report)
    _write_new_text(markdown_path, _markdown(report))
    print(json.dumps({
        "status": report["status"],
        "candidate_count": report["candidate_count"],
        "selected_candidate_id": selected["candidate_id"],
        "selected_profile": selected["profile"],
        "selected_learning_rate": selected["learning_rate"],
        "selected_l2": selected["l2"],
        "selected_validation": selected["metrics"]["validation"],
        "selected_test_oos_diagnostic": selected["metrics"]["test_oos"],
        "input_sha256": report["input"]["sha256"],
        "code_commit": code_commit,
        "report": str(report_path),
        "markdown": str(markdown_path),
        "can_trade": False,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
