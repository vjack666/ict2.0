from datetime import date
import json

from scripts import run_mechanical_bot_monthly as runner


def test_runner_persists_artifact_events_and_status(tmp_path, monkeypatch):
    def fake_replay(_data_dir, _start, _end, *, events_path, progress=None):
        events_path.write_text('{"kind":"CLOSE","net_pnl_usd":1}\n', encoding="utf-8")
        return {"summary": {"net_pnl_usd": 1}, "events": [{"kind": "CLOSE"}], "input_sha256": {"M1": "abc"}}

    monkeypatch.setattr(runner, "run_month_from_parquets", fake_replay)
    monkeypatch.setattr(runner, "generate_report", lambda source, output: {"source": str(source), "output": str(output)})
    result = runner.run_month(start=date(2026, 8, 1), end=date(2026, 8, 1), output_dir=tmp_path / "out", data_dir=tmp_path / "data")
    assert result["artifact"]["status"] == "FINALIZADO_DIAGNOSTIC_ONLY"
    assert (tmp_path / "out" / "events.jsonl").is_file()
    assert json.loads((tmp_path / "out" / "status.json").read_text(encoding="utf-8"))["state"] == "FINALIZADO"
