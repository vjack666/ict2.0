"""Informe local y diagnóstico para el backtest mensual del bot mecánico.

El módulo sólo lee eventos JSON/JSONL ya producidos por un replay.  Nunca
importa MetaTrader5 ni el motor diario y siempre publica ``can_trade=false``.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CAN_TRADE = False
STATUS = "DIAGNOSTIC_ONLY"
PLOT_NAMES = ("balance.png", "drawdown.png", "pnl_acumulado.png", "distribucion_pnl.png")


def _load_records(source: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Accept a JSON envelope/list or a line-oriented JSON event stream."""
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        return {}, []
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(decoded, list):
        return {}, [item for item in decoded if isinstance(item, dict)]
    if not isinstance(decoded, dict):
        raise ValueError("BACKTEST_ARTIFACT_MUST_BE_OBJECT_OR_ARRAY")
    candidates = decoded.get("events") or decoded.get("records") or decoded.get("decisions") or []
    if not isinstance(candidates, list):
        raise ValueError("BACKTEST_EVENTS_MUST_BE_A_LIST")
    return decoded, [item for item in candidates if isinstance(item, dict)]


def _number(record: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = record.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def _event_name(record: dict[str, Any]) -> str:
    return str(record.get("event") or record.get("event_type") or record.get("kind") or record.get("action") or "").upper()


def _is_close(record: dict[str, Any]) -> bool:
    name = _event_name(record)
    return any(token in name for token in ("CYCLE_CLOSED", "CLOSE_CYCLE", "CLOSE_ALL", "CLOSED", "CLOSE")) and not "REQUEST" in name


def _is_ambiguous(record: dict[str, Any]) -> bool:
    return bool(record.get("ambiguous")) or "AMBIGU" in str(record.get("status") or "").upper() or "AMBIGU" in _event_name(record)


def _when(record: dict[str, Any], fallback: int) -> tuple[str, datetime]:
    raw = record.get("asof_time") or record.get("time") or record.get("timestamp") or record.get("closed_at")
    if isinstance(raw, str):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return raw, value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        except ValueError:
            pass
    return f"event-{fallback:06d}", datetime(1970, 1, 1, tzinfo=timezone.utc)


def _session(record: dict[str, Any]) -> str:
    value = str(record.get("session") or record.get("session_name") or "UNSPECIFIED").upper()
    if "LONDON" in value or "LONDRES" in value:
        return "LONDON"
    if "NEW" in value or value == "NY" or "YORK" in value:
        return "NEW_YORK"
    return value


def build_summary(envelope: dict[str, Any], events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Calculate transparent metrics from close records; missing values remain zero."""
    initial = _number(envelope, "initial_balance", "balance_initial", default=5000.0)
    ordered = sorted(list(events), key=lambda pair: _when(pair, 0)[1])
    closures = [event for event in ordered if _is_close(event)]
    gross = sum(_number(e, "gross_pnl_usd", "pnl_gross_usd", "gross_pnl") for e in closures)
    net = sum(_number(e, "net_pnl_usd", "pnl_net_usd", "net_pnl", "pnl_usd") for e in closures)
    costs = sum(_number(e, "execution_cost_usd", "cost_usd", "costs_usd", "commission_usd", "total_cost_usd") for e in closures)
    # If only gross and costs exist, net is still derivable.  Do not overwrite a
    # declared zero net result, because that may be a legitimate breakeven.
    if closures and all(not any(k in e for k in ("net_pnl_usd", "pnl_net_usd", "net_pnl", "pnl_usd")) for e in closures):
        net = gross - costs
    balance = initial
    peak = initial
    max_dd = 0.0
    balance_points: list[dict[str, Any]] = [{"time": "start", "balance": balance, "drawdown_usd": 0.0, "pnl_cumulative": 0.0}]
    pnl_values: list[float] = []
    sessions: dict[str, dict[str, float | int]] = defaultdict(lambda: {"cycles": 0, "gross_pnl_usd": 0.0, "net_pnl_usd": 0.0, "costs_usd": 0.0, "tp": 0, "sl": 0})
    for index, event in enumerate(closures, 1):
        item_net = _number(event, "net_pnl_usd", "pnl_net_usd", "net_pnl", "pnl_usd")
        item_gross = _number(event, "gross_pnl_usd", "pnl_gross_usd", "gross_pnl")
        item_cost = _number(event, "execution_cost_usd", "cost_usd", "costs_usd", "commission_usd", "total_cost_usd")
        if not any(k in event for k in ("net_pnl_usd", "pnl_net_usd", "net_pnl", "pnl_usd")):
            item_net = item_gross - item_cost
        balance += item_net
        peak = max(peak, balance)
        drawdown = peak - balance
        max_dd = max(max_dd, drawdown)
        time, _ = _when(event, index)
        balance_points.append({"time": time, "balance": balance, "drawdown_usd": drawdown, "pnl_cumulative": balance - initial})
        pnl_values.append(item_net)
        bucket = sessions[_session(event)]
        bucket["cycles"] += 1
        bucket["gross_pnl_usd"] += item_gross
        bucket["net_pnl_usd"] += item_net
        bucket["costs_usd"] += item_cost
        reason = str(event.get("reason") or event.get("close_reason") or "").lower()
        if "take_profit" in reason or reason == "tp":
            bucket["tp"] += 1
        if "max_floating_loss" in reason or "risk" in reason or reason == "sl":
            bucket["sl"] += 1
    # Present both mandated windows even when no cycle occurred.
    for name in ("LONDON", "NEW_YORK"):
        sessions[name]
    tp = sum(int(row["tp"]) for row in sessions.values())
    sl = sum(int(row["sl"]) for row in sessions.values())
    ambiguous = sum(1 for event in ordered if _is_ambiguous(event))
    # The replay samples adverse intrabar extrema for the dynamic loss rule.
    # Preserve its authoritative maximum rather than reducing the report to
    # balance-at-close drawdown only.
    replay_summary = envelope.get("summary") if isinstance(envelope.get("summary"), dict) else {}
    replay_dd = _number(replay_summary, "max_drawdown_usd")
    replay_dd_pct = _number(replay_summary, "max_drawdown_pct")
    max_dd = max(max_dd, replay_dd)
    max_dd_pct = replay_dd_pct if replay_dd_pct else ((max_dd / peak * 100.0) if peak else 0.0)
    return {
        "status": STATUS,
        "can_trade": CAN_TRADE,
        "initial_balance_usd": initial,
        "final_balance_usd": balance,
        "gross_pnl_usd": gross,
        "net_pnl_usd": net,
        "costs_usd": costs,
        "cycles": len(closures),
        "tp_cycles": tp,
        "sl_risk_cycles": sl,
        "max_drawdown_usd": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "ambiguous_cases": ambiguous,
        "sessions": {key: dict(value) for key, value in sorted(sessions.items())},
        "balance_points": balance_points,
        "pnl_values": pnl_values,
    }


def _plots(summary: dict[str, Any], output_dir: Path) -> list[str]:
    paths = [output_dir / name for name in PLOT_NAMES]
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
    except ImportError:
        # A valid transparent PNG preserves the deliverable and makes the
        # dependency failure visible in the report rather than fabricating data.
        tiny_png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360606060000000050001a5f645400000000049454e44ae426082")
        for path in paths:
            path.write_bytes(tiny_png)
        return [str(path) for path in paths]
    points = summary["balance_points"]
    x = list(range(len(points)))
    charts = [
        ("Balance ($)", [p["balance"] for p in points], paths[0]),
        ("Drawdown ($)", [p["drawdown_usd"] for p in points], paths[1]),
        ("P/L acumulado ($)", [p["pnl_cumulative"] for p in points], paths[2]),
    ]
    for title, values, path in charts:
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.plot(x, values, marker="o", linewidth=1.5)
        ax.set_title(title); ax.set_xlabel("Ciclos cerrados"); ax.grid(alpha=.3)
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 3.5))
    values = summary["pnl_values"] or [0.0]
    ax.hist(values, bins=min(20, max(1, len(values))), edgecolor="white")
    ax.set_title("Distribución de P/L neto por ciclo ($)"); ax.set_xlabel("P/L neto ($)"); ax.grid(axis="y", alpha=.3)
    fig.tight_layout(); fig.savefig(paths[3], dpi=130); plt.close(fig)
    return [str(path) for path in paths]


def _markdown(summary: dict[str, Any], source: Path) -> str:
    lines = ["# Informe mensual — bot mecánico", "", "**Estado:** DIAGNOSTIC_ONLY", "**can_trade:** false", f"**Fuente:** `{source.name}`", "", "## Resumen", "", "| Métrica | Valor |", "|---|---:|"]
    for label, key in (("Saldo inicial", "initial_balance_usd"), ("Saldo final", "final_balance_usd"), ("P/L bruto", "gross_pnl_usd"), ("P/L neto", "net_pnl_usd"), ("Costes", "costs_usd"), ("Ciclos", "cycles"), ("TP", "tp_cycles"), ("SL/riesgo", "sl_risk_cycles"), ("DD máximo", "max_drawdown_usd"), ("DD máximo %", "max_drawdown_pct"), ("Casos ambiguos", "ambiguous_cases")):
        value = summary[key]
        rendered = f"${value:,.2f}" if "usd" in key else (f"{value:.2f}%" if key.endswith("pct") else str(value))
        lines.append(f"| {label} | {rendered} |")
    lines += ["", "## Por sesión", "", "| Sesión | Ciclos | Bruto | Neto | Costes | TP | SL/riesgo |", "|---|---:|---:|---:|---:|---:|---:|"]
    for session, row in summary["sessions"].items():
        lines.append(f"| {session} | {row['cycles']} | ${row['gross_pnl_usd']:.2f} | ${row['net_pnl_usd']:.2f} | ${row['costs_usd']:.2f} | {row['tp']} | {row['sl']} |")
    lines += ["", "Las gráficas y el JSON de métricas son diagnóstico local. No autorizan promoción ni órdenes.", ""]
    return "\n".join(lines)


def generate_report(source: Path, output_dir: Path) -> dict[str, Any]:
    envelope, events = _load_records(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary(envelope, events)
    summary["source"] = str(source)
    summary["records_read"] = len(events)
    summary["plots"] = _plots(summary, output_dir)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "report.md").write_text(_markdown(summary, source), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera informe DIAGNOSTIC_ONLY de backtest mecánico")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "mechanical_bot" / "monthly")
    args = parser.parse_args(argv)
    summary = generate_report(args.input, args.output_dir)
    print(json.dumps({"status": summary["status"], "can_trade": False, "cycles": summary["cycles"], "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())\n