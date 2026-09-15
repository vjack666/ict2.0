from types import SimpleNamespace
from datetime import datetime, timezone
import json

import pytest

from mechanical_bot.core import BotAction
from mechanical_bot.blackbox import BlackBoxJournal
from mechanical_bot.mt5_adapter import MT5Adapter


class FakeMT5:
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0
    ACCOUNT_TRADE_MODE_DEMO = 0

    def __init__(self, retcode=10009):
        self.retcode = retcode
        self.requests = []
        self.rows = [SimpleNamespace(ticket=10, symbol="EURUSD", magic=42, type=0, volume=.1, price_open=1.1, profit=1.0), SimpleNamespace(ticket=11, symbol="EURUSD", magic=9, type=0, volume=.1, price_open=1.1, profit=1.0)]

    def symbol_info_tick(self, _symbol):
        return SimpleNamespace(ask=1.2, bid=1.1)

    def order_send(self, request):
        self.requests.append(request)
        if self.retcode == 10009 and "position" in request:
            self.rows = [row for row in self.rows if row.ticket != request["position"]]
        return SimpleNamespace(retcode=self.retcode, order=7, deal=8)

    def positions_get(self, symbol=None):
        return [row for row in self.rows if symbol is None or row.symbol == symbol]

    def last_error(self):
        return (0, "OK")


def _journal(tmp_path):
    return BlackBoxJournal(tmp_path / "blackbox.jsonl", max_bytes=100_000)


def test_disabled_adapter_never_sends_order():
    mt5 = FakeMT5()
    adapter = MT5Adapter(mt5=mt5, execution_enabled=False)
    with pytest.raises(RuntimeError, match="disabled"):
        adapter.execute(BotAction("OPEN", "test", "BUY", .1), symbol="EURUSD", magic_number=42)
    assert mt5.requests == []


def test_string_execution_flag_never_enables_orders():
    mt5 = FakeMT5()
    adapter = MT5Adapter(mt5=mt5, execution_enabled="false")
    with pytest.raises(RuntimeError, match="disabled"):
        adapter.execute(BotAction("OPEN", "test", "BUY", .1), symbol="EURUSD", magic_number=42)
    assert mt5.requests == []


def test_open_uses_bot_magic_and_requires_mt5_success(tmp_path):
    mt5 = FakeMT5()
    journal = _journal(tmp_path)
    adapter = MT5Adapter(mt5=mt5, execution_enabled=True, blackbox=journal)
    result = adapter.execute(BotAction("OPEN", "test", "BUY", .1), symbol="EURUSD", magic_number=42)
    assert result[0]["kind"] == "OPEN"
    assert mt5.requests[0]["magic"] == 42 and mt5.requests[0]["volume"] == .1
    events = [json.loads(line) for line in journal.path.read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events] == ["ORDER_REQUEST", "ORDER_RESULT"]
    assert events[0]["request_hash"] == events[1]["request_hash"]
    assert events[1]["result"]["retcode"] == 10009

    rejected = MT5Adapter(mt5=FakeMT5(retcode=10016), execution_enabled=True, blackbox=_journal(tmp_path / "rejected"))
    with pytest.raises(RuntimeError, match="retcode=10016"):
        rejected.execute(BotAction("OPEN", "test", "BUY", .1), symbol="EURUSD", magic_number=42)


def test_order_send_passes_mapping_positionally_without_losing_fields(tmp_path):
    class NativeSignatureMT5(FakeMT5):
        def order_send(self, request, /):
            self.requests.append(request)
            return SimpleNamespace(retcode=10009, order=7, deal=8)

    mt5 = NativeSignatureMT5()
    # Live 5.0.5735 returns 10013 with an empty TradeRequest for a named
    # mapping. A positional-only double prevents that regression locally.
    with pytest.raises(TypeError):
        mt5.order_send(request={"symbol": "EURUSD"})
    result = MT5Adapter(mt5=mt5, execution_enabled=True, blackbox=_journal(tmp_path)).execute(
        BotAction("OPEN", "test", "BUY", .1), symbol="EURUSD", magic_number=42,
    )
    assert result[0]["retcode"] == 10009
    assert mt5.requests[0]["symbol"] == "EURUSD"
    assert mt5.requests[0]["magic"] == 42
    assert mt5.requests[0]["volume"] == .1
    assert len(mt5.requests) == 1


def test_close_only_targets_matching_symbol_and_magic_number(tmp_path):
    mt5 = FakeMT5()
    adapter = MT5Adapter(mt5=mt5, execution_enabled=True, blackbox=_journal(tmp_path))
    adapter.execute(BotAction("CLOSE_ALL", "test"), symbol="EURUSD", magic_number=42)
    assert [request["position"] for request in mt5.requests] == [10]


def test_partial_or_absent_close_is_not_reported_as_complete(tmp_path):
    partial = MT5Adapter(mt5=FakeMT5(retcode=10010), execution_enabled=True, blackbox=_journal(tmp_path / "partial"))
    with pytest.raises(RuntimeError, match="positions remain"):
        partial.execute(BotAction("CLOSE_ALL", "test"), symbol="EURUSD", magic_number=42)

    empty_mt5 = FakeMT5()
    empty_mt5.rows = []
    empty = MT5Adapter(mt5=empty_mt5, execution_enabled=True, blackbox=_journal(tmp_path / "empty"))
    with pytest.raises(RuntimeError, match="no matching"):
        empty.execute(BotAction("CLOSE_ALL", "test"), symbol="EURUSD", magic_number=42)


def test_pre_send_blackbox_failure_blocks_order_send(tmp_path):
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("file", encoding="utf-8")
    journal = BlackBoxJournal(blocked_parent / "blackbox.jsonl", max_bytes=100_000)
    mt5 = FakeMT5()
    adapter = MT5Adapter(mt5=mt5, execution_enabled=True, blackbox=journal)
    with pytest.raises(RuntimeError, match="pre-send persistence"):
        adapter.execute(BotAction("OPEN", "test", "BUY", .1), symbol="EURUSD", magic_number=42)
    assert mt5.requests == []


def test_m15_readiness_uses_only_closed_fresh_candles():
    class CandleMT5(FakeMT5):
        TIMEFRAME_M15 = 15

        def __init__(self):
            super().__init__()
            self.copy_args = None

        def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
            self.copy_args = (symbol, timeframe, start_pos, count)
            now = int(datetime.now(timezone.utc).timestamp())
            last_closed = (now // 900 - 1) * 900
            return [{"time": last_closed, "high": 1.2, "low": 1.0, "close": 1.1} for _ in range(count)]

    mt5 = CandleMT5()
    candles = MT5Adapter(mt5=mt5, execution_enabled=False).closed_m15_candles("EURUSD", count=20)
    assert mt5.copy_args == ("EURUSD", mt5.TIMEFRAME_M15, 1, 20)
    assert len(candles) == 20


@pytest.mark.parametrize(("opened_at", "now_epoch", "message"), [
    (1_800, 2_699, "still open"),
    (3_600, 2_700, "future"),
    (0, 3_000, "stale"),
])
def test_m15_epoch_guard_rejects_open_future_and_expired_bars(opened_at, now_epoch, message):
    with pytest.raises(RuntimeError, match=message):
        MT5Adapter._assert_closed_m15_epoch(opened_at, now_epoch=now_epoch)


def test_m15_epoch_guard_accepts_closed_utc_epoch_without_broker_offset():
    MT5Adapter._assert_closed_m15_epoch(1_800, now_epoch=2_701)


def test_nonzero_broker_offset_is_rejected_instead_of_applied():
    with pytest.raises(ValueError, match="already UTC"):
        MT5Adapter(mt5=FakeMT5(), server_utc_offset_seconds=10_800)
