import time, json, pandas as pd
import numpy as np
import engine.mtf_navigation as M

print("loading H1/H4/D1 parquet...", flush=True)
t0 = time.time()
frames = {tf: pd.read_parquet(f'data/raw/EURUSD/EURUSD_{tf}.parquet').sort_values('time').reset_index(drop=True)
          for tf in ('D1', 'H4', 'H1')}
print(f"loaded {[ (tf, len(frames[tf])) for tf in frames ]} in {time.time()-t0:.1f}s", flush=True)

print("init (precompute_sequences=True)...", flush=True)
t1 = time.time()
nav = M.MTFNavigator(frames, M.NavigatorConfig(precompute_sequences=True, sequence_tf='H1'))
print(f"init done in {time.time()-t1:.1f}s", flush=True)

h1 = frames['H1']
n = 200
times = [h1['time'].iloc[i] for i in range(500, 500 + n*50, 50)][:n]
print(f"navigate {n} times...", flush=True)
t2 = time.time()
states = [nav.navigate(t, exec_tf='H1') for t in times]
dt = time.time() - t2
print(f"navigate {n} in {dt:.2f}s -> {dt/n*1000:.1f} ms/bar", flush=True)

# sanity: show one state
s = states[0]
print("sample status:", s.status, "layers:", list(s.layers.keys()), flush=True)
print("D1 bias:", s.layers.get('D1').structure_bias.value if s.layers.get('D1') else None, flush=True)
