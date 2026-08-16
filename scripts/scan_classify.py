"""Escáner de clasificación ORIENTADO A DEFICIENCIAS (ICT SYSTEM).

No es una taxonomía plana: cada módulo lleva ejes + una lista de códigos de
defecto (defects) para que se puedan BUSCAR problemas con jq/grep.

Salida:
  data/classification/manifest.json
  data/classification/INDEX.md

NO hace commit ni push.
"""
from __future__ import annotations

import os
import re
import json
import datetime
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIRS = ["tools", "detectors", "engine", "agents"]
OUT_DIR = os.path.join(ROOT, "data", "classification")
os.makedirs(OUT_DIR, exist_ok=True)

PY_RE = re.compile(r"\.py$")
CACHE_RE = re.compile(r"__pycache__")


def walk_py(d: str):
    for root, dirs, files in os.walk(os.path.join(ROOT, d)):
        if CACHE_RE.search(root):
            continue
        for f in sorted(files):
            if PY_RE.search(f):
                yield os.path.relpath(os.path.join(root, f), ROOT)


def count_loc(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return sum(1 for _ in fh)
    except Exception:
        return 0


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


# ---- role heuristics ----
def infer_role(name: str, text: str) -> str:
    n = name.lower()
    if "test" in n:
        return "util"
    if "detect" in n or n in ("bos", "choch", "fvg", "liquidity", "killzones",
                              "ob", "trend", "fib", "gaps", "zones", "swing"):
        return "detector"
    if "score" in n or "quality" in n or n == "choch":
        return "scorer"
    if "state" in n:
        return "state"
    if "adapter" in n or "from_tools" in n:
        return "adapter"
    if "feed" in n or "data" in n:
        return "feed"
    if "exec" in n or "dealing" in n:
        return "executor"
    if "narrative" in n or "htf" in n or "labels" in n:
        return "narrative"
    if "agent" in n or "orchestr" in n or n == "base":
        return "orchestrator"
    return "util"


# ---- cross-repo import map for ORPHAN detection ----
ALL_PY = []
for d in SCAN_DIRS:
    ALL_PY += [p.replace("\\", "/") for p in walk_py(d)]

TEXT_CACHE = {p: read_text(os.path.join(ROOT, p)) for p in ALL_PY}


def is_orphan(path: str) -> bool:
    base = os.path.splitext(os.path.basename(path))[0]
    if base in ("__init__", "base"):
        return False
    pat = re.compile(r"\b" + re.escape(base) + r"\b")
    hits = 0
    for p, txt in TEXT_CACHE.items():
        if p == path:
            continue
        if pat.search(txt):
            hits += 1
            break
    return hits == 0


# ---- defect detection ----
HARDCODED_PAT = re.compile(r">=\s*(85|70|0\.55|0\.5|2)\b")
MODEL_LOAD_PAT = re.compile(r"model\.joblib|RandomForest|GradientBoosting|joblib\.load")
IA_DISABLE_PAT = re.compile(r"CHOCH_IA_DISABLE")


def detect_defects(path: str, text: str, role: str) -> tuple[list[str], str]:
    defects: list[str] = []
    notes = []

    # NO_TESTS: no existe tests/ en el repo
    tests_dir = os.path.join(ROOT, "tests")
    if not os.path.isdir(tests_dir):
        defects.append("NO_TESTS")
        notes.append("no existe directorio tests/ en el repo")

    # ORPHAN
    if is_orphan(path):
        defects.append("ORPHAN")
        notes.append("no es importado por ningún otro módulo escaneado")

    # HARDCODED_THRESHOLD
    m = HARDCODED_PAT.search(text)
    if m:
        defects.append("HARDCODED_THRESHOLD")
        notes.append(f"umbral mágico no parametrizado (~'{m.group(0)}')")

    # DUPLICATE: quality_score (tools) solapa con engine bos quality
    if os.path.basename(path) == "quality_score.py":
        defects.append("DUPLICATE")
        notes.append("lógica de quality solapa con engine bos/structure quality")

    # OVERCALIBRATED: score híbrido CHOCH reportado saturado (index v2)
    if os.path.basename(path) == "choch_quality.py":
        defects.append("OVERCALIBRATED")
        notes.append("index F2: 'todos los CHOCH salen premium' -> score saturado arriba")

    # UNVERIFIED: tools/ recién creados sin validación documentada
    if path.startswith("tools/") and "verified" not in text.lower() \
            and "test" not in text.lower():
        defects.append("UNVERIFIED")
        notes.append("herramienta tools/ nueva, sin validación contra datos documentada")

    return defects, "; ".join(notes)


# ---- maturity / verification / lineage / owner ----
def infer_meta(path: str, text: str) -> tuple[str, str, str, str]:
    layer = path.split("/", 1)[0]
    if layer == "tools":
        lineage = "isolated"
        owner = "ict_agent"
    elif layer == "detectors":
        lineage = "coupled"
        owner = "ict_agent"
    elif layer == "agents":
        lineage = "coupled"
        owner = "ict_agent"
    else:  # engine
        lineage = "coupled"
        owner = "structure_agent"

    maturity = "experimental"
    verification = "partial"
    if path.startswith("tools/"):
        maturity = "experimental"
        verification = "unverified"
    if "deprecated" in text.lower() or "obsolete" in text.lower():
        maturity = "deprecated"
    return maturity, verification, lineage, owner


modules = []
for p in ALL_PY:
    if os.path.basename(p) == "__init__.py":
        # keep only if non-trivial
        txt0 = TEXT_CACHE[p]
        if len(txt0.strip()) < 5:
            continue
    txt = TEXT_CACHE[p]
    name = os.path.splitext(os.path.basename(p))[0]
    role = infer_role(name, txt)
    maturity, verification, lineage, owner = infer_meta(p, txt)
    defects, note = detect_defects(p, txt, role)
    modules.append({
        "path": p,
        "name": name,
        "layer": p.split("/", 1)[0],
        "role": role,
        "maturity": maturity,
        "verification": verification,
        "lineage": lineage,
        "owner": owner,
        "defects": defects,
        "notes": note,
        "loc": count_loc(os.path.join(ROOT, p)),
    })

modules.sort(key=lambda m: m["path"])

# ---- events_summary (aggregated) ----
events_summary = []
choch_dir = os.path.join(ROOT, "data", "learning", "choch")
bos_dir = os.path.join(ROOT, "data", "learning", "bos")

# choch model/train status
train_path = os.path.join(choch_dir, "2026-08", "train_report.json")
roc_auc = None
validation = "unvalidated"
calibration = "ok"
note_ev = ""
if os.path.isfile(train_path):
    try:
        tr = json.load(open(train_path, encoding="utf-8"))
        roc_auc = float(tr.get("best", {}).get("test_auc") or tr.get("best", {}).get("cv_auc"))
        validation = "ia_rated" if roc_auc and roc_auc >= 0.55 else "unvalidated"
        note_ev = tr.get("verdict", "")
    except Exception as e:
        note_ev = f"train_report ilegible: {e}"

# count choch / bos jsonl records
def count_jsonl(d: str) -> int:
    c = 0
    if not os.path.isdir(d):
        return 0
    for f in os.listdir(d):
        if f.endswith(".jsonl"):
            fp = os.path.join(d, f)
            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if line.strip():
                        c += 1
    return c

choch_total = count_jsonl(choch_dir)
bos_total = count_jsonl(bos_dir)

# by_class from jsonl extra (choch) if present
cls_counter = Counter()
real_count = 0
for f in os.listdir(choch_dir):
    if f.endswith(".jsonl"):
        with open(os.path.join(choch_dir, f), "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                extra = obj.get("extra", {}) or {}
                cl = extra.get("choch_class")
                if cl:
                    cls_counter[cl] += 1
                if extra.get("choch_real"):
                    real_count += 1

events_summary.append({
    "source": "data/learning/choch",
    "total_records": choch_total,
    "by_class": dict(cls_counter),
    "real_count": real_count,
    "validation": validation,
    "calibration": "over",
    "roc_auc": roc_auc,
    "note": note_ev + (" | by_class vacío en jsonl: el scorer escribe choch_class "
                        "en runtime, no en estos jsonl de eventos crudos." if not cls_counter else ""),
})
events_summary.append({
    "source": "data/learning/bos",
    "total_records": bos_total,
    "by_class": {},
    "real_count": None,
    "validation": "unvalidated",
    "calibration": "ok",
    "roc_auc": None,
    "note": "BOS crudos sin score de calidad ni validación IA.",
})

manifest = {
    "generated_utc": datetime.datetime.utcnow().isoformat() + "Z",
    "modules": modules,
    "events_summary": events_summary,
}

with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)

# ---- INDEX.md ----
layer_counts = Counter(m["layer"] for m in modules)
defect_counter = Counter()
for m in modules:
    for d in m["defects"]:
        defect_counter[d] += 1

lines = []
lines.append("# Índice de Clasificación por Deficiencia — ICT SYSTEM\n")
lines.append(f"- **Generado (UTC):** {manifest['generated_utc']}")
lines.append(f"- **Total módulos escaneados:** {len(modules)}\n")
lines.append("## Conteo por layer\n")
lines.append("| Layer | Módulos |")
lines.append("|---|---|")
for layer in ("tools", "detectors", "engine", "agents"):
    lines.append(f"| {layer} | {layer_counts.get(layer,0)} |")
lines.append("")
lines.append("## Top defect-codes\n")
lines.append("| Código | Módulos afectados |")
lines.append("|---|---|")
for code, n in defect_counter.most_common(10):
    lines.append(f"| {code} | {n} |")
lines.append("")
lines.append("## Módulos por layer (con defects)\n")
for layer in ("tools", "detectors", "engine", "agents"):
    lines.append(f"### {layer}\n")
    lines.append("| módulo | role | maturity | verif | lineage | defects |")
    lines.append("|---|---|---|---|---|---|")
    for m in modules:
        if m["layer"] != layer:
            continue
        df = ", ".join(m["defects"]) or "—"
        lines.append(f"| `{m['path']}` | {m['role']} | {m['maturity']} | "
                     f"{m['verification']} | {m['lineage']} | {df} |")
    lines.append("")
lines.append("## Eventos BOS/CHOCH (agregado)\n")
for ev in events_summary:
    lines.append(f"### {ev['source']}")
    lines.append(f"- total_records: {ev['total_records']}")
    lines.append(f"- by_class: {ev['by_class']}")
    lines.append(f"- real_count: {ev['real_count']}")
    lines.append(f"- validation: {ev['validation']}")
    lines.append(f"- calibration: {ev['calibration']}")
    lines.append(f"- roc_auc: {ev['roc_auc']}")
    lines.append(f"- note: {ev['note']}\n")

with open(os.path.join(OUT_DIR, "INDEX.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))

# ---- console summary ----
print("=== SCAN COMPLETE ===")
print(f"modules: {len(modules)} | by layer: {dict(layer_counts)}")
print(f"top defects: {defect_counter.most_common(8)}")
print(f"choch records: {choch_total} | bos records: {bos_total}")
print(f"choch validation: {validation} | roc_auc: {roc_auc}")
print(f"calibration(per index): over")
print(f"wrote: {os.path.join(OUT_DIR,'manifest.json')} and INDEX.md")
