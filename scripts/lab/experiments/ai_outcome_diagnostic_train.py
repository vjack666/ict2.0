"""Runner LOCAL_ONLY DIAGNOSTIC_ONLY para un JSONL de outcomes causal."""
from __future__ import annotations

import argparse
import json
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True, type=Path, help="JSONL causal materializado")
    parser.add_argument("--output", required=True, type=Path, help="artefacto JSON nuevo")
    parser.add_argument("--target", default="label_end_6")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--min-class-rows", type=int, default=5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run_diagnostic_training(
            args.jsonl,
            target=args.target,
            seed=args.seed,
            iterations=args.iterations,
            learning_rate=args.learning_rate,
            l2=args.l2,
            min_class_rows=args.min_class_rows,
        )
        output = write_diagnostic_artifact(payload, args.output)
    except DiagnosticTrainingError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "status": payload["status"],
        "reason_code": payload.get("reason_code"),
        "fit_executed": payload["fit_executed"],
        "output": str(output),
        "can_trade": payload["can_trade"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] == "DIAGNOSTIC_ONLY_COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
