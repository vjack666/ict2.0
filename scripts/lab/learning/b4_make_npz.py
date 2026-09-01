"""B4 aux — Solo genera nature_head_data.npz (X,y + split) sin reentrenar.

Reusa _nature_targets de train_nature_head (rango 2022-2026, Opción A).
Guarda X,y,idx,n_tr para que b4_nature_eval corra instantáneo.
Mucho mas rapido que reentrenar (solo build_tf_blocks, sin epochs torch).
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, ".")
import numpy as np
import importlib.util as _u

_spec = _u.spec_from_file_location("tnh_mod", "scripts/lab/learning/train_nature_head.py")
tnh = _u.module_from_spec(_spec)
_spec.loader.exec_module(tnh)

X, y = tnh._nature_targets()
n = len(X)
rng = np.random.RandomState(42)
idx = rng.permutation(n)
n_tr = int(n * 0.8)
np.savez("data/learning/encoder/nature_head_data.npz", X=X, y=y, idx=idx, n_tr=n_tr)
print(f"NPZ guardado: {n} muestras (confirm={int(y.sum())}, {100*y.mean():.1f}%) -> nature_head_data.npz")
