from __future__ import annotations

import json

from scripts.report_mechanical_bot_monthly import build_summary, generate_report


def test_generates_diagnostic_report_and_all_charts(tmp_path):
    source = tmp_path / "events.jsonl"
    events = [
        {"event": "CYCLE_CLOSED", "session": "LONDON", "asof_time": "2026-08-03T10:00:00Z", "gross_pnl_usd": 68, "net_pnl_usd": 60, "cost_usd": 8, "reason": "take_profit_aggregate"},
        {"event": "CYCLE_CLOSED", "session": "NEW_YORK", "asof_time": "2026-08-03T15:00:00Z", "gross_pnl_usd": -90, "net_pnl_usd": -100, "cost_usd": 10, "reason": "max_floating_loss", "ambiguous": True},
    ]
    source.write_text("\n".join(json.dumps(item) for item in events), encoding="utf-8")
    result = generate_report(source, tmp_path / "report")
    assert result["status"] == "DIAGNOSTIC_ONLY"
    assert result["can_trade"] is False
    assert result["cycles"] == 2
    assert result["net_pnl_usd"] == -40
    assert result["max_drawdown_usd"] == 100
    assert result["sessions"]["LONDON"]["tp"] == 1
    assert result["sessions"]["NEW_YORK"]["sl"] == 1
    assert result["ambiguous_cases"] == 1
    assert (tmp_path / "report" / "summary.json").is_file()
    assert (tmp_path / "report" / "report.md").read_text(encoding="utf-8").find("can_trade:** false") >= 0
    assert all((tmp_path / "report" / name).is_file() for name in ("balance.png", "drawdown.png", "pnl_acumulado.png", "distribucion_pnl.png"))


def test_derives_net_when_only_gross_and_cost_exist():
    summary = build_summary({"initial_balance": 5000}, [{"event": "CLOSE_ALL", "gross_pnl_usd": 70, "cost_usd": 10, "session": "London"}])
    assert summary["net_pnl_usd"] == 60
    assert summary["final_balance_usd"] == 5060
    assert summary["sessions"]["LONDON"]["cycles"] == 1


def test_core_close_kind_is_counted_but_close_request_is_not():
    summary = build_summary(
        {"initial_balance": 5000},
        [
            {"kind": "CLOSE", "net_pnl_usd": 60, "session": "London"},
            {"kind": "CLOSE_REQUEST", "net_pnl_usd": -999, "session": "London"},
        ],
    )
    assert summary["cycles"] == 1
    assert summary["net_pnl_usd"] == 60


def test_report_preserves_conservative_intrabar_drawdown_from_replay_artifact():
    summary = build_summary(
        {"initial_balance": 5000, "summary": {"max_drawdown_usd": 125, "max_drawdown_pct": 2.5}},
        [{"kind": "CLOSE", "net_pnl_usd": -100, "session": "London"}],
    )
    assert summary["max_drawdown_usd"] == 125
    assert summary["max_drawdown_pct"] == 2.5
