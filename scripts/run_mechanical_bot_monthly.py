"""Run one persisted, diagnostic-only monthly mechanical-bot replay.

This entry point never imports MetaTrader5 and does not start a loop.  It
creates the state and artifacts before returning so a completed run is always
auditable, even if its terminal is later closed.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import traceback
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.mechanical_bot_monthly import run_month_from_parquets
from scripts.report_mechanical_bot_monthly import generate_report


DEFAULT_OUTPUT = ROOT / "reports" / "mechanical_bot" / "2026-08"


def _status(path: Path, state: str, **extra: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "state": state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "can_trade": False,
        "mode": "DIAGNOSTIC_ONLY",
        **extra,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def run_month(*, start: date, end: date, output_dir: Path, data_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "status.json"
    events_path = output_dir / "events.jsonl"
    artifact_path = output_dir / "backtest.json"
    _status(status_path, "RUNNING", period={"start": str(start), "end": str(end)}, events_path=str(events_path))
    try:
        def progress(trading_day: date, completed_days: int, total_days: int) -> None:
            _status(status_path, "RUNNING", period={"start": str(start), "end": str(end)},
                    current_trading_day=str(trading_day), completed_days=completed_days,
                    total_days=total_days, events_path=str(events_path))

        artifact = run_month_from_parquets(data_dir, start, end, events_path=events_path, progress=progress)
        artifact["status"] = "FINALIZADO_DIAGNOSTIC_ONLY"
        artifact_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        report = generate_report(artifact_path, output_dir)
        _status(status_path, "FINALIZADO", artifact_path=str(artifact_path), events_path=str(events_path),
                report_summary=str(output_dir / "summary.json"), summary=artifact["summary"])
        return {"artifact": artifact, "report": report, "output_dir": str(output_dir)}
    except Exception as exc:
        _status(status_path, "FAILED", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecuta una sola corrida mensual del bot mecánico, sin MT5.")
    parser.add_argument("--start", default="2026-08-01")
    parser.add_argument("--end", default="2026-08-31")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw" / "EURUSD")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if end < start:
        parser.error("--end debe ser igual o posterior a --start")
    result = run_month(start=start, end=end, output_dir=args.output_dir, data_dir=args.data_dir)
    summary = result["artifact"]["summary"]
    print(json.dumps({"status": "FINALIZADO", "can_trade": False, "output_dir": result["output_dir"], **summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
