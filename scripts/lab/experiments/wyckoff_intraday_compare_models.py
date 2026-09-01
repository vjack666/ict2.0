"""Compara perfiles ICT-only, Wyckoff-only y combinados sobre un corpus fijo.

La comparación es diagnóstica: reutiliza el mismo JSONL causal, etiqueta,
semilla y split temporal. No crea una registry, no toca MT5 y no autoriza
trading ni promoción científica.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

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
DEFAULT_OUTPUT = ROOT / "reports" / "audits" / "experiments" / "ai" / "wyckoff_intraday_2006_2010_comparison"
TARGET = "label_end_12"
SEED = 20260831
VARIANTS = (
    ("ICT_ONLY", "ict_only"),
    ("WYCKOFF_ONLY", "wyckoff_only"),
    ("WYCKOFF_ICT_COMBINED", "wyckoff_ict_combined"),
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"salida ya existe y no se sobrescribe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_new_text(path: Path, text: str) -> None:
    if path.exists():
        raise SystemExit(f"salida ya existe y no se sobrescribe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _comparison_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Comparación diagnóstica ICT-only vs Wyckoff-only vs combinado",
        "",
        f"- **Estado:** `{report['status']}`",
        f"- **Corpus:** `{report['input']['path']}`",
        f"- **Filas:** {report['input']['rows']}",
        f"- **Hash corpus:** `{report['input']['sha256']}`",
        f"- **Etiqueta:** `{report['target']}`",
        "- **Modo:** `DIAGNOSTIC_ONLY`; `can_trade=false`; sin promoción",
        "",
        "## Métricas",
        "",
        "| Variante | Features | Train acc. | Validation acc. | Test/OOS acc. | Test/OOS log-loss | Δ vs mayoría |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["variants"]:
        metrics = item["metrics"]
        lines.append(
            f"| {item['profile']} | {item['feature_count']} | "
            f"{metrics['train']['accuracy']:.6f} | "
            f"{metrics['validation']['accuracy']:.6f} | "
            f"{metrics['test_oos']['accuracy']:.6f} | "
            f"{metrics['test_oos']['log_loss']:.6f} | "
            f"{item['test_accuracy_delta_vs_majority']:+.6f} |"
        )
    lines.extend([
        "",
        "## Lectura",
        "",
        "La tabla solo permite comparar el aporte incremental de cada perfil.",
        "No demuestra edge ni rentabilidad. El TEST/OOS permanece fuera del ajuste;",
        "el holdout cronológico 2021–2025 sigue reservado para una fase posterior.",
        "",
        "## Controles",
        "",
        "- Mismo JSONL, hash de entrada y etiqueta para las tres variantes.",
        "- Mismo split temporal 60/20/20, semilla y algoritmo determinista.",
        "- Sin `DatasetSnapshot` certificado, sin `ModelRegistry`, sin MT5 y sin órdenes.",
        "- Provenance/licencia histórica permanece en `REVIEW/BLOCKED` hasta resolverla.",
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
        raise SystemExit(f"directorio de comparación no vacío; no se sobrescribe: {output_dir}")

    rows = load_causal_jsonl(source, target=TARGET)
    code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    variants: list[dict[str, Any]] = []
    input_hashes: set[str] = set()
    split_shapes: set[str] = set()
    for profile, slug in VARIANTS:
        feature_names = INTRADAY_FEATURE_PROFILES[profile]
        diagnostic = run_diagnostic_training(
            source,
            target=TARGET,
            seed=SEED,
            code_commit=code_commit,
            feature_names=feature_names,
        )
        artifact_path = output_dir / f"{slug}.json"
        write_diagnostic_artifact(diagnostic, artifact_path)
        metrics = diagnostic.get("metrics", {})
        test = metrics.get("test_oos", {})
        class_counts = test.get("class_counts", {})
        test_rows = int(test.get("rows", 0))
        majority_accuracy = max(class_counts.values()) / test_rows if test_rows else 0.0
        input_hashes.add(str(diagnostic["input"]["sha256"]))
        split_shapes.add(json.dumps(diagnostic["temporal_split"], sort_keys=True))
        variants.append({
            "profile": profile,
            "slug": slug,
            "artifact": str(artifact_path),
            "artifact_file_sha256": _file_sha256(artifact_path),
            "artifact_hash": diagnostic["artifact_hash"],
            "source_code_commit": diagnostic["model"]["source_code_commit"],
            "feature_count": len(feature_names),
            "feature_names": list(feature_names),
            "status": diagnostic["status"],
            "fit_executed": diagnostic["fit_executed"],
            "can_trade": diagnostic["can_trade"],
            "metrics": metrics,
            "test_majority_baseline_accuracy": majority_accuracy,
            "test_accuracy_delta_vs_majority": float(test.get("accuracy", 0.0) - majority_accuracy),
            "test_uniform_baseline_log_loss": 1.0986122886681098,
        })

    if len(input_hashes) != 1 or len(split_shapes) != 1:
        raise SystemExit("las variantes no comparten exactamente input hash y split temporal")
    if any(item["status"] != "DIAGNOSTIC_ONLY_COMPLETED" for item in variants):
        raise SystemExit("una variante no completó el ajuste diagnóstico")
    if any(item["source_code_commit"] != code_commit for item in variants):
        raise SystemExit("una variante no referencia el commit actual")

    report = {
        "schema_version": "1.0",
        "status": "DIAGNOSTIC_COMPARISON_COMPLETED",
        "mode": "DIAGNOSTIC_ONLY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_commit": code_commit,
        "target": TARGET,
        "seed": SEED,
        "input": {
            "path": str(source),
            "rows": len(rows.rows),
            "sha256": next(iter(input_hashes)),
            "schema_hash": rows.schema_hash,
        },
        "same_temporal_split": True,
        "holdout_2021_2025_used": False,
        "can_trade": False,
        "shadow_mode": True,
        "scientific_training_eligible": False,
        "variants": variants,
        "next_action": "Auditar comparación, luego ejecutar holdout 2021-2025 sin ajuste y revisar calibración/abstención/drift.",
    }
    report["report_hash"] = hashlib.sha256(_canonical(report)).hexdigest()
    report_path = output_dir / "comparison.json"
    markdown_path = output_dir / "comparison.md"
    _write_new_json(report_path, report)
    _write_new_text(markdown_path, _comparison_markdown(report))
    print(json.dumps({
        "status": report["status"],
        "report": str(report_path),
        "markdown": str(markdown_path),
        "input_sha256": report["input"]["sha256"],
        "code_commit": code_commit,
        "variants": [
            {
                "profile": item["profile"],
                "test_accuracy": item["metrics"]["test_oos"]["accuracy"],
                "test_log_loss": item["metrics"]["test_oos"]["log_loss"],
                "delta_vs_majority": item["test_accuracy_delta_vs_majority"],
            }
            for item in variants
        ],
        "can_trade": False,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
