"""Auditoria INDEPENDIENTE del dataset regenerado (stdlib + replica de la
logica de context_bucket). No importa la fabrica para no heredar sus dependencias
ni su hash canonico; recalcula todo desde cero. Falla cerrado (exit!=0) si hay
cualquier inconsistencia."""
import json, hashlib, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/learning/seq_ctx_01"

def bias_name(v):
    if isinstance(v, dict):  # Enum
        v = v.get("value", v)
    return str(v).upper() if v is not None else "UNKNOWN"

def direction_sign(d):
    try:
        s = int(d)
    except (TypeError, ValueError):
        return {"BULLISH": 1, "BEARISH": -1, "BULL": 1, "BEAR": -1}.get(str(d).upper())
    return s if s in (1, -1) else None

def h1_alignment(seq_dir, h1_bias):
    s = direction_sign(seq_dir); b = bias_name(h1_bias)
    if s is None or b not in ("BULLISH", "BEARISH"):
        return "NEUTRAL"
    return "ALIGNED" if (1 if b == "BULLISH" else -1) == s else "AGAINST"

def context_bucket(seq_dir, d1_bias, h4_loc, h1_align):
    s = direction_sign(seq_dir)
    if s is None:
        return "NEUTRAL"
    score = 0
    d1 = bias_name(d1_bias)
    if d1 in ("BULLISH", "BEARISH"):
        score += 1 if (1 if d1 == "BULLISH" else -1) == s else -1
    loc = bias_name(h4_loc)
    if loc in ("DISCOUNT", "PREMIUM"):
        score += 1 if (1 if loc == "DISCOUNT" else -1) == s else -1
    a = bias_name(h1_align)
    if a == "ALIGNED": score += 1
    elif a == "AGAINST": score -= 1
    if score >= 2: return "ALIGNED"
    if score <= -2: return "AGAINST"
    return "NEUTRAL"

def has_label(d):
    if isinstance(d, dict):
        return any(str(k).startswith("label_") or has_label(v) for k, v in d.items())
    if isinstance(d, list):
        return any(has_label(x) for x in d)
    return False

def canonical_hash(rows):
    norm = []
    for r in rows:
        item = dict(r); item.pop("dataset_sha256", None)
        norm.append(json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str))
    return hashlib.sha256(("\n".join(norm) + "\n").encode()).hexdigest()

def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    errs = 0
    print("=== FASE 3: AUDITORIA INDEPENDIENTE (stdlib) ===")
    for did in ["SEQ_CTX_01_CANONICAL_BOS", "SEQ_CTX_01_LITE"]:
        rows = [json.loads(l) for l in open(OUT / f"{did}.jsonl", encoding="utf") if l.strip()]
        mhash = manifest["datasets"][did]["sha256"]
        chash = canonical_hash(rows)
        ok_h = chash == mhash
        ids = [r["event_id"] for r in rows]; dup = len(ids) - len(set(ids))
        ct_bad = sum(1 for r in rows if r["can_trade"] is not False)
        ctx_missing = 0; bucket_bad = 0; leak = 0
        for r in rows:
            ci = r.get("features_at_t", {}).get("context_inputs", {})
            if not all(k in ci and ci[k] is not None for k in ("sequence_direction", "d1_bias", "h4_location", "h1_alignment")):
                ctx_missing += 1
            exp = context_bucket(r["direction"], ci.get("d1_bias"), ci.get("h4_location"), ci.get("h1_alignment"))
            if exp != r["context_bucket"]:
                bucket_bad += 1
            if has_label(r["features_at_t"]):
                leak += 1
        print(f"\n{did}: rows={len(rows)}")
        print(f"  hash==manifest: {ok_h} ({chash[:12]}..)")
        print(f"  dup_event_id={dup} can_trade!=false={ct_bad} ctx_missing={ctx_missing} bucket_bad={bucket_bad} leak={leak}")
        errs += int(not ok_h) + dup + ct_bad + ctx_missing + bucket_bad + leak
    print("\n=== RESULTADO ===")
    if errs == 0:
        print("PASS — integridad certificada (independiente)")
        return 0
    print(f"FAIL — {errs} errores")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
