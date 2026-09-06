from types import SimpleNamespace

import pytest

from mechanical_bot.core import BotAction
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

    def symbol_info_tick(self, _symbol):
        return SimpleNamespace(ask=1.2, bid=1.1)

    def order_send(self, request):
        self.requests.append(request)
        return SimpleNamespace(retcode=self.retcode, order=7, deal=8)

    def positions_get(self, symbol=None):
        return [SimpleNamespace(ticket=10, symbol="EURUSD", magic=42, type=0, volume=.1, price_open=1.1, profit=1.0), SimpleNamespace(ticket=11, symbol="EURUSD", magic=9, type=0, volume=.1, price_open=1.1, profit=1.0)]


def test_disabled_adapter_never_sends_order():
    mt5 = FakeMT5()
    adapter = MT5Adapter(mt5=mt5, execution_enabled=False)
    with pytest.raises(RuntimeError, match="disabled"):
        adapter.execute(BotAction("OPEN", "test", "BUY", .1), symbol="EURUSD", magic_number=42)
    assert mt5.requests == []


def test_open_uses_bot_magic_and_requires_mt5_success():
    mt5 = FakeMT5()
    adapter = MT5Adapter(mt5=mt5, execution_enabled=True)
    result = adapter.execute(BotAction("OPEN", "test", "BUY", .1), symbol="EURUSD", magic_number=42)
    assert result[0]["kind"] == "OPEN"
    assert mt5.requests[0]["magic"] == 42 and mt5.requests[0]["volume"] == .1

    rejected = MT5Adapter(mt5=FakeMT5(retcode=10016), execution_enabled=True)
    with pytest.raises(RuntimeError, match="retcode=10016"):
        rejected.execute(BotAction("OPEN", "test", "BUY", .1), symbol="EURUSD", magic_number=42)


def test_close_only_targets_matching_symbol_and_magic_number():
    mt5 = FakeMT5()
    adapter = MT5Adapter(mt5=mt5, execution_enabled=True)
    adapter.execute(BotAction("CLOSE_ALL", "test"), symbol="EURUSD", magic_number=42)
    assert [request["position"] for request in mt5.requests] == [10]
