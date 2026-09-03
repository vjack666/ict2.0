"""Read-only local MT5 feed for the scanner viewer."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import MetaTrader5 as mt5
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.mt5_operational_snapshot import build_mt5_operational_snapshot

ROOT = r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"
TF_MAP = {"H4": mt5.TIMEFRAME_H4, "H1": mt5.TIMEFRAME_H1, "M15": mt5.TIMEFRAME_M15, "M5": mt5.TIMEFRAME_M5, "M1": mt5.TIMEFRAME_M1}

def artifact(symbol="EURUSD", count=400):
    if not mt5.initialize(path=ROOT): raise RuntimeError(f"MT5_INIT_FAILED:{mt5.last_error()}")
    try:
        frames = {}
        for tf, code in TF_MAP.items():
            rates = mt5.copy_rates_from_pos(symbol, code, 1, count)  # skip open bar
            if rates is None or len(rates) == 0: raise RuntimeError(f"MT5_NO_DATA:{symbol}:{tf}:{mt5.last_error()}")
            rows = []
            for i, row in enumerate(rates):
                stamp = datetime.fromtimestamp(int(row["time"]), timezone.utc).isoformat()
                rows.append({"index": i, "tf": tf, "time": stamp, "observation_time": stamp, "open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"])})
            frames[tf] = rows
        timeline = frames["M5"]
        frame_map = {tf: pd.DataFrame(rows) for tf, rows in frames.items()}
        decision_time = timeline[-1]["observation_time"]
        engine_snapshot = build_mt5_operational_snapshot(frame_map, decision_time, symbol=symbol, required_tfs=("H4", "H1", "M15", "M5"))
        zones = []
        for tf, items in engine_snapshot.get("canonical_zones", {}).items():
            for item in items:
                if isinstance(item, dict):
                    item = {**item, "tf": tf, "authority_tf": item.get("authority_tf", tf)}
                    if "high" in item and "low" in item: zones.append(item)
        structure = []
        for tf, layer in (engine_snapshot.get("context_state") or {}).get("layers", {}).items():
            if layer.get("last_bos_bar") is not None:
                structure.append({"id": f"bos-{tf}", "tf": tf, "kind": "BOS", "bar": int(layer["last_bos_bar"]), "direction": layer.get("last_bos_direction"), "observation_time": layer.get("asof_time")})
        return {"schema_version":"2.0", "artifact_kind":"MTF_REPLAY", "symbol":symbol, "run_metadata":{"source":"MT5_LOCAL","engine":"MT5_OPERATIONAL_SNAPSHOT_V1","generated_at":datetime.now(timezone.utc).isoformat()}, "policy":{"diagnostic_only":True,"entry_authorized":False,"can_trade":False,"can_train":False,"promotion_authorized":False}, "profiles":[], "candles_by_tf":frames, "timeline":timeline, "market_state_checkpoints":[],"state_deltas":[],"setups":zones,"structure_events":structure,"episodes":[],"invalidations":[],"trades":[],"rejections":[], "engine_snapshot":engine_snapshot, "live_status":"READY_MT5_CLOSED_ONLY"}
    finally: mt5.shutdown()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try: payload = artifact()
        except Exception as exc: payload = {"live_status":"BLOCKED", "error":str(exc), "candles_by_tf":{}, "timeline":[], "setups":[], "episodes":[], "invalidations":[], "trades":[], "rejections":[], "state_deltas":[]}
        body = json.dumps(payload).encode()
        self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_): pass

if __name__ == "__main__": ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
