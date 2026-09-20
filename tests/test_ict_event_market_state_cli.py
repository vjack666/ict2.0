"""CLI tests: explicit inventory provenance; no invented accepted episodes."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

MODULE = Path(__file__).resolve().parents[1]/'scripts/audit/ict_event_market_state.py'
spec = importlib.util.spec_from_file_location('ict_event_market_state_cli', MODULE)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_cli_dedup_preserves_non_certified_status(tmp_path):
    csv=tmp_path/'events.csv'
    row={'control':'B','tf':'M1','tipo':'FVG','direccion':1,'confirmation_time_utc':'2026-08-24T20:34Z',
         'nivel':1.099,'zone_high':1.100,'source_close':1.101}
    pd.DataFrame([row,row]).to_csv(csv,index=False)
    summary=cli.run(csv,control='B',output=tmp_path/'summary.json')
    assert summary['inventory_rows']==2 and summary['unique_detector_marketobjects']==1
    assert summary['accepted_episodes_count'] is None
    assert summary['gates']['P1_FULL_FUNNEL']=='NOT_RUN'


def test_cli_rejects_previous_geometry_free_inventory_and_missing_control(tmp_path):
    csv=tmp_path/'old.csv'
    pd.DataFrame([{'control':'B','tf':'M1','tipo':'FVG','direccion':1,
                   'confirmation_time_utc':'2026-08-24T20:34Z','nivel':1.099}]).to_csv(csv,index=False)
    with pytest.raises(ValueError,match='geometry'):
        cli.run(csv,control='B',output=tmp_path/'o.json')
    csv.unlink()
    with pytest.raises(FileNotFoundError):
        cli.run(csv,control='B',output=tmp_path/'o.json')
