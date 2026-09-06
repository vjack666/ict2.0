from scripts.export_visual_backtest import _parser, _required_timeframes


def test_narrow_ltf_request_keeps_h4_and_execution_context():
    args = _parser().parse_args(["--tfs", "M15", "M5", "M1"])
    assert _required_timeframes(args) == ("M15", "M5", "M1", "H4")
    assert args.htf_timeframe == "H4"
    assert args.execution_timeframe == "M5"


def test_context_can_be_explicitly_changed_for_a_diagnostic_replay():
    args = _parser().parse_args([
        "--tfs", "M15", "M1", "--htf-timeframe", "H1",
        "--execution-timeframe", "M1",
    ])
    assert _required_timeframes(args) == ("M15", "M1", "H1")


def test_multitf_mode_keeps_the_full_d1_h4_h1_context_stack():
    args = _parser().parse_args(["--tfs", "M15", "M5", "M1", "--multitf-context"])

    assert _required_timeframes(args) == ("M15", "M5", "M1", "D1", "H4", "H1")
