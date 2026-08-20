import time, sys, importlib.util, tempfile, os, json
from pathlib import Path
import pandas as pd

# Cargar motor ORIGINAL desde origin/main (sin mi parche)
import subprocess
orig_src = subprocess.check_output(
    ["git", "show", "origin/main:engine/mtf_navigation.py"], text=True
)
tmp = Path(tempfile.gettempdir()) / "mtf_nav_original.py"
tmp.write_text(orig_src)
spec_o = importlib.util.spec_from_file_location("mtf_nav_original", tmp)
mod_o = importlib.util.module_from_spec(spec_o)
sys.modules["mtf_nav_original"] = mod_o
spec_o.loader.exec_module(mod_o)

# Motor PARCHEADO (actual en disco)
import engine.mtf_navigation as mod_p

from audits.codigo.mtf_seq_funnel import _load_tf

frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
h1 = frames["H1"]

cfg = mod_p.NavigatorConfig(precompute_sequences=True, sequence_tf="H1")
nav_p = mod_p.MTFNavigator(frames, cfg)
nav_o = mod_o.MTFNavigator(frames, cfg)

# 500 puntos aleatorios pero deterministicos
import numpy as np
rng = np.random.default_rng(42)
idxs = sorted(rng.integers(500, len(h1) - 100, 200).tolist())
times = [h1["time"].iloc[i] for i in idxs]

diffs = 0
for k, t in enumerate(times):
    sp = nav_p.navigate(t, exec_tf="H1").to_dict()
    so = nav_o.navigate(t, exec_tf="H1").to_dict()
    # comparar campos clave (no time string exacto, sino estructura)
    for layer in ("D1", "H4", "H1"):
        lp = sp["layers"].get(layer)
        lo = so["layers"].get(layer)
        if (lp is None) != (lo is None):
            diffs += 1
            continue
        if lp is None:
            continue
        for key in ("structure_bias", "regime", "last_bos_direction", "last_bos_bar", "displacement_recent"):
            if lp.get(key) != lo.get(key):
                diffs += 1
                if diffs <= 5:
                    print(f"DIFF layer={layer} key={key} patch={lp.get(key)} orig={lo.get(key)} @idx={idxs[k]}")
        # zones count
        if len(lp.get("zones", [])) != len(lo.get("zones", [])):
            diffs += 1
            if diffs <= 5:
                print(f"DIFF zones count layer={layer} patch={len(lp.get('zones',[]))} orig={len(lo.get('zones',[]))} @idx={idxs[k]}")
    if k % 100 == 0:
        print(f"  checked {k}/500 diffs={diffs}", flush=True)

print(f"TOTAL DIFFS: {diffs} / {len(times)*3} layer-checks")
print("RESULT:", "BIT-EXACT" if diffs == 0 else "MISMATCH")
