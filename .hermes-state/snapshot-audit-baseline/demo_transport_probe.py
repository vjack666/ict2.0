"""One-shot user-authorized demo transport test; not a strategy signal."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent.parents[2]s[2]
sys.path.insert(0, str(ROOT))
from mechanical_bot.mt5_adapter import MT5Adapter
from mechanical_bot.core import BotAction
from mechanical_bot.blackbox import BlackBoxJournal

LOGIN = 10011586708
SERVER = "MetaQuotes-Demo"
SYMBOL = "EURUSD"
MAGIC = 26091099
OUT = Path(__file__).parent
report = {"scope": "DEMO_TRANSPORT_ONLY_NOT_STRATEGY", "started_at": datetime.now(timezone.utc).isoformat(),
          "magic": MAGIC, "volume": 0.01, "orders": [], "status": "BLOCKED"}
adapter = MT5Adapter(terminal_path=r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe",
    execution_enabled=True, demo_account_login=LOGIN, demo_account_server=SERVER,
    server_utc_offset_seconds=10800, blackbox=BlackBoxJournal(OUT / "demo_transport_blackbox.jsonl"))
correlation = str(uuid4())
opened_attempt = False
try:
    adapter.connect()
    adapter._assert_demo_guard()
    mt5 = adapter._mt5
    account = mt5.account_info()
    if account.margin_mode != mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING:
        raise RuntimeError("Hedging account required to preserve existing positions")
    if not account.trade_allowed or not account.trade_expert:
        raise RuntimeError("Demo account does not allow expert trading")
    info = mt5.symbol_info(SYMBOL)
    if info is None or not info.visible or info.volume_min > 0.01:
        raise RuntimeError("Symbol unavailable or minimum lot exceeds 0.01")
    def positions():
        rows = mt5.positions_get(symbol=SYMBOL)
        if rows is None:
            raise RuntimeError("Position reconciliation unavailable")
        return list(rows)
    before = positions()
    if any(p.magic == MAGIC for p in before):
        raise RuntimeError("Test magic already has a position; no new order allowed")
    report["unrelated_before"] = [{"ticket": p.ticket, "volume": p.volume, "type": p.type} for p in before]
    # Pin and freshness checks run again inside the canonical adapter before send.
    adapter.tick_price(SYMBOL, "BUY")
    opened_attempt = True
    report["orders"].extend(adapter.execute(BotAction("OPEN", "USER_AUTHORIZED_DEMO_TRANSPORT_TEST", "BUY", 0.01),
        symbol=SYMBOL, magic_number=MAGIC, correlation_id=correlation))
    owned = [p for p in positions() if p.magic == MAGIC]
    if len(owned) != 1 or abs(owned[0].volume - 0.01) > 1e-8:
        raise RuntimeError("Unexpected test position; reconciliation required")
    report["opened_ticket"] = owned[0].ticket
    report["status"] = "OPEN_CONFIRMED"
except Exception as exc:
    report["error"] = str(exc)
finally:
    if opened_attempt:
        try:
            adapter._assert_demo_guard()
            owned = [p for p in positions() if p.magic == MAGIC]
            if owned:
                report["orders"].extend(adapter.execute(BotAction("CLOSE_ALL", "DEMO_TEST_IMMEDIATE_CLEANUP"),
                    symbol=SYMBOL, magic_number=MAGIC, correlation_id=correlation))
            remaining = positions()
            report["test_positions_remaining"] = len([p for p in remaining if p.magic == MAGIC])
            report["unrelated_after"] = [{"ticket": p.ticket, "volume": p.volume, "type": p.type} for p in remaining if p.magic != MAGIC]
            if report["status"] == "OPEN_CONFIRMED" and report["test_positions_remaining"] == 0 and report["unrelated_after"] == report["unrelated_before"]:
                report["status"] = "PASS_OPEN_CLOSE_RECONCILED"
        except Exception as exc:
            report["cleanup_error"] = str(exc)
            report["status"] = "RECONCILIATION_REQUIRED"
    adapter.close()
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    (OUT / "demo_transport_result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
