"""Ejecución OOS finita y parametrizable: H4 solo frente a contexto completo.

Ejecuta exactamente dos replays locales y termina. No reintenta, no crea
órdenes y deja estado atómico para que el resultado sea auditable.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]


def _write(path: Path, body: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _status(path: Path, state: str, step: str | None, **extra: object) -> None:
    _write(path, {
        "state": state, "current_step": step, "updated_at": datetime.now(timezone.utc).isoformat(),
        "can_trade": False, "diagnostic_only": True, **extra,
    })


def _run(output_dir: Path, name: str, *, multitf: bool, start: str, data_end: str) -> Path:
    output = output_dir / f"{name}_backtest.json"
    command = [
        sys.executable, "scripts/export_visual_backtest.py", "--symbol", "EURUSD",
        "--timeframe", "M15", "--tfs", "M15", "M5", "M1",
        "--data-dir", "data/raw/EURUSD", "--start", start, "--end", data_end,
        "--horizon-bars", "200", "--output", str(output),
    ]
    if multitf:
        command.append("--multitf-context")
    log = output_dir / f"{name}.log"
    with log.open("w", encoding="utf-8") as stream:
        subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
    return output


def _metrics(path: Path, *, oos_end: str, data_end: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    signals = [
        signal for signal in payload["signals"]
        if str(signal.get("decision_time", "")) <= oos_end
    ]
    trades = [
        trade for trade in payload["trades"]
        if str(trade.get("entry_time", "")) <= oos_end
    ]
    resolved = [trade for trade in trades if trade.get("outcome") in {"TP", "SL"}]
    return {
        "signals": len(signals),
        "trades": len(trades),
        "resolved": len(resolved),
        "tp": sum(trade.get("outcome") == "TP" for trade in resolved),
        "sl": sum(trade.get("outcome") == "SL" for trade in resolved),
        "open_or_unresolved": len(trades) - len(resolved),
        "resolution_buffer_end": data_end,
        "excluded_post_oos_trades": len(payload["trades"]) - len(trades),
        "direction_flip_invalidations": sum(
            row.get("reason") == "DIRECTION_FLIP"
            for row in payload["metadata"]["sequence_audit"].get("invalidations", [])
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--oos-end", required=True)
    parser.add_argument("--data-end", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = ROOT / args.output_dir
    if output_dir.exists():
        raise SystemExit(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    status = output_dir / "status.json"
    try:
        _status(status, "RUNNING", "H4_ONLY", completed=[])
        h4 = _run(output_dir, "h4_only", multitf=False, start=args.start, data_end=args.data_end)
        _status(status, "RUNNING", "FULL_CONTEXT", completed=["H4_ONLY"])
        full = _run(output_dir, "full_context", multitf=True, start=args.start, data_end=args.data_end)
        summary = {
            "status": "COMPLETED_DIAGNOSTIC_ONLY", "can_trade": False, "diagnostic_only": True,
            "scope": "FIXED_OOS_WINDOW_CONTEXT_COMPARISON", "start": args.start, "oos_end": args.oos_end,
            "data_end_with_resolution_buffer": args.data_end, "horizon_bars": 200,
            "h4_only": _metrics(h4, oos_end=args.oos_end, data_end=args.data_end),
            "full_context": _metrics(full, oos_end=args.oos_end, data_end=args.data_end),
            "note": "TP/SL only are outcomes; OPEN remains unresolved.",
        }
        _write(output_dir / "summary.json", summary)
        _status(status, "FINALIZADO", None, completed=["H4_ONLY", "FULL_CONTEXT"], summary=str(output_dir / "summary.json"))
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        _status(status, "FAILED", None, error=str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
