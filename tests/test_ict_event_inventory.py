"""Alcance: inventario de detectores, NO certifica el funnel ni P1 completo."""
import importlib.util
from pathlib import Path
import pandas as pd
import pytest

MODULE = Path(__file__).resolve().parents[1] / 'scripts/audit/ict_event_inventory.py'
spec = importlib.util.spec_from_file_location('ict_event_inventory', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_frozen_control_timestamps_and_selected_sources():
    assert audit.CONTROLS == {'A':'2026-09-17T18:20:00Z', 'B':'2026-08-24T20:35:00Z'}
    assert audit.MEMBERS['M5'] == 'EURUSD/EURUSD_M5_3m.csv'
    assert audit.MEMBERS['M1'] == 'EURUSD/EURUSD_M1.csv'


def test_context_poll_is_not_ict_event():
    # El bug anterior contaba 30 lecturas x 3 TF aunque bos_dir=0.
    with pytest.raises(ValueError, match='zero direction'):
        audit.event_identity('H1','BOS',pd.Timestamp('2026-08-24T20:35Z'),0)
    a=audit.event_identity('H1','BOS',pd.Timestamp('2026-08-24T20:30Z'),1)
    assert a==audit.event_identity('H1','BOS',pd.Timestamp('2026-08-24T20:30Z'),1)
    assert a!=audit.event_identity('H1','BOS',pd.Timestamp('2026-08-24T20:31Z'),1)


def test_control_b_open_bar_is_not_closed():
    control=pd.Timestamp(audit.CONTROLS['B'])
    opened=pd.Timestamp('2026-08-24T20:35:00Z')
    previous=opened-pd.Timedelta(minutes=1)
    assert previous+pd.Timedelta(minutes=1)<=control
    assert opened+pd.Timedelta(minutes=1)>control


def test_manifest_sha_rejects_incorrect_bytes(tmp_path):
    import json,zipfile
    member='EURUSD/EURUSD_M5_3m.csv'
    path=tmp_path/'tiny.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr(member,'time,open\n2026-08-24T20:00:00Z,1.0\n')
    m=tmp_path/'manifest.json'
    m.write_text(json.dumps({'files':[{'filename':'EURUSD_M5_3m.csv','sha256':'0'*64}],
       'recent_window_source_selection':{'M5':{'selected':'EURUSD_M5_3m.csv'}}}))
    old=audit.MEMBERS
    try:
        audit.MEMBERS={'M5':member}
        with zipfile.ZipFile(path) as z:
            with pytest.raises(AssertionError,match='SHA256'):
                audit.verify_sha256_manifest(z,m)
    finally:audit.MEMBERS=old
