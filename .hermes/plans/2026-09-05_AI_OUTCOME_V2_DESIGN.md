# Design: AI Outcome Classifier v2 — Engine-Connected Retraining

**Change:** ai-outcome-v2
**Date:** 2026-09-05
**Status:** DESIGN (→ tasks)
**Proposal:** `.hermes/plans/2026-09-05_AI_OUTCOME_V2_PROPOSAL.md`
**Spec:** `.hermes/plans/2026-09-05_AI_OUTCOME_V2_SPEC.md`
**Scope gate:** This design adds nothing beyond the proposal/spec. No invented requirements. All technical names below are canonical for sdd-tasks.
**Global constraints (inherited, non-negotiable):** `can_trade=false` entire mission; no MT5; `engine/` read-only; no circular optimization; no `git push`; no `TRAINING_ELIGIBLE` declaration (this run is `DIAGNOSTIC_ONLY`); no "edge" language. Baseline artifacts byte-for-byte untouched.

---

## 1. Technical Approach

Retrain the existing outcome classifier on the **canonical engine funnel** (`engine/episodes.py`) instead of the legacy `backtest/replay.py` bridge. A new **adapter** converts each funnel event into a causal `features_at_t` dict (per feature set A–F), a new **materializer** writes the v2 JSONL (same hash/schema/source discipline as `diagnostic_training.load_causal_jsonl`), and the existing `training_pipeline` + `train_outcome_classifier` are reused through the existing `diagnostic_training` DIAGNOSTIC_ONLY path. Everything new is additive under `scripts/lab/experiments/` plus a registry extension in `runtime/ai_learning/outcome_classifier.py`.

The v1 pipeline and baseline artifacts are structurally untouched: we **do not** modify `_intraday_features`, `FEATURE_NAMES`, `INTRADAY_*` constants, or the existing `INTRADAY_FEATURE_PROFILES` values. Compatibility is guaranteed by **never mutating existing tuples** and by dispatching new profiles through a **separate v2 feature vector builder** selected in `_features` by a new registry key, not by rewriting the intraday path.

---

## 2. Architecture Overview

```
                    ENGINE (read-only, unmodified)
   engine/episodes.py  build_episodes(ms, decisions_T, ctx)
        └─ funnel artifact { records[], episodes[], rejections[],
                             aggregates, gates, checksum }
                                │
                                ▼
   scripts/lab/experiments/ai_outcome_v2_adapter.py
     per-event causal extraction → features_at_t {A..F}
     (MTFNavigator.navigate / ContextConstraints / LayerSnapshot /
      canonical zones / BOS HTF / M5/M1 / permissions / lineage / reason)
                                │
                                ▼
   scripts/lab/experiments/ai_outcome_v2_dataset.py
     materializer → ai_outcome_v2.jsonl + audit dataset
     (raw_sha256, schema_hash, strict-increasing event_time,
      future-feature scan, forbidden-field scan, tri-state guard)
                                │
                                ▼
   runtime/ai_learning/diagnostic_training.run_diagnostic_training()
     load_causal_jsonl → TemporalSplit (60/20/20) → train_outcome_classifier
        └─ outcome_classifier._features dispatch (v2 register A–F)
                                │
                                ▼
   scripts/lab/experiments/ai_outcome_v2_ablation.py  (A→F, equality of experiment)
   scripts/lab/experiments/ai_outcome_v2_eval.py      (OOS + per-segment + baseline)
        └─ classification into 6 categories + gates G0–G13 evidence
```

The old chain `backtest/replay.py → ai_outcome_funnel_bridge.py → ai_outcome_dataset.py` is **not** touched and remains the v1 source. The new chain reads only `build_episodes` output. `backtest/` and `engine/` are never imported by the v2 materializer for data; `engine/` is only consumed (read-only) by the adapter for the canonical funnel and the context-state/zone/BOS/M5/M1 sources it needs to produce `features_at_t`.

> Adapter input provenance note: `build_episodes` returns `Episode`/`FunnelRecord` *dicts*. The richer per-event fields (`context_state`, `direction_hint`, `regime_stack`, `allow_long/allow_short`, zones, BOS layers, M5/M1 micro) are NOT inside the funnel artifact's `Episode` defs as-is; the adapter recomputes them **causally at `time <= decision_time`** by re-invoking the same `MTFNavigator.navigate(decision_time, exec_tf="H1")` that the operational snapshot uses. This is allowed because navigation is deterministic and forward-PIT (only closed bars `<= decision_time`). The funnel rows that lack a full context (early-stage rejects like `MISSING_SNAPSHOT`) yield a degenerate-but-valid `features_at_t` (UNKNOWN / NO_OPINION everywhere) and are preserved in the audit set with their `reason`.

---

## 3. Adapter Design (`ai_outcome_v2_adapter.py`)

### 3.1 Module surface

```python
# scripts/lab/experiments/ai_outcome_v2_adapter.py
CONTRACT_VERSION = "AI_OUTCOME_V2_ADAPTER_V1"
FUNNEL_CONTRACT_VERSION = "EPISODES_FUNNEL_V1"   # consumed, not imported for data
FEATURE_SET_NAMES = ("A", "B", "C", "D", "E", "F")

class AdapterError(ValueError): ...

@dataclass(frozen=True)
class AdaptedEvent:
    episode_id: str            # funnel identity (or f"AUDIT_{candidate_key_hash}")
    decision_time: str         # ISO-8601 UTC
    direction: int             # -1/0/1 (0 where funnel had no direction)
    status: str                # ACCEPTED | REJECTED | SUPERSEDED
    reason: str                # funnel REASONS code ("" for ACCEPTED)
    lineage_depth: int
    lineage_count: int
    features_at_t: dict        # full v2 feature payload (superset of A–F)
    can_trade: bool = False

def adapt_funnel_artifact(
    funnel: Mapping[str, Any] | str | Path,
    navigator_loader,           # callable -> MTFNavigator (causal)
    *,
    frames: Mapping[str, Any],  # TF -> OHLC (closed-bar source for navigator)
    context_ctx=None,
) -> AdaptedResult: ...

@dataclass(frozen=True)
class AdaptedResult:
    events: tuple[AdaptedEvent, ...]
    audit: tuple[dict[str, Any], ...]     # rejected candidates w/ reason, preserved
    diagnostics: tuple[str, ...]
    funnel_row_count: int
    adapted_row_count: int
    reason_counts: dict[str, int]
```

The adapter iterates `records[]` (every `FunnelRecord`) + `episodes[]` + `rejections[]`. **Every accepted, rejected, and superseded candidate becomes a candidate row** — nothing is silently dropped (spec §1, gate G7).

### 3.2 Per-event causal extraction rules (features_at_t)

For each event at `decision_time`, the adapter computes `navigate(decision_time, exec_tf="H1")` and serializes the `MarketState`/`ContextConstraints`/`LayerSnapshot` causally (`time <= decision_time`). Extraction mapped to the spec fields:

| v2 `features_at_t` block | Source (causal) | Encoding |
|---|---|---|
| `context_state.layer_status` | `MarketState.status` + per-layer presence | one-hot D1/H4/H1 × `OK/INCOMPLETE/BLOCKED` (missing layer ⇒ INCOMPLETE) |
| `context_state.direction_hint` | `ContextConstraints.direction_hint` (`StructureBias`) | one-hot BULLISH/BEARISH/MIXED/UNKNOWN |
| `context_state.regime_stack` | `ContextConstraints.regime_stack` (per layer `RegimeLabel`) | one-hot per layer × `TREND_BULL/TREND_BEAR/RANGE/EXPANSION/RETRACEMENT/COMPRESSION/UNKNOWN` |
| `context_state.location` | H4 `WHERE_IN_CONTEXT.location` | numeric/one-hot DISCOUNT/PREMIUM/EQUILIBRIUM/MID/OUTSIDE |
| `context_state.bos_htf` | per-layer `LayerSnapshot.last_bos_direction` (D1/H4/H1) | 2 bools/layer: `bos_bullish`, `bos_bearish` (None ⇒ both False **but flagged separately** — this is a binary-optional field, NOT tri-state; tri-state applies only to permissions) |
| `zones` | `ContextConstraints.location_zones` + `liquidity_targets` (Zone.kind) | counts POI/BSL/SSL/DEALING + proximity to `last_close` (numeric) |
| `lifecycle.stage` | `Episode.status` → SETUP/ELIGIBLE/BLOCKED/SUPERSEDED/OUT_OF_CONTEXT | one-hot |
| `M5.m5_bos/m5_displacement/m5_fvg` | M5 micro from `_answer_ltf`/LayerSnapshot (displacement_recent) + M5 BOS/FVG detection at `time<=decision_time` | bools (each 2-state; **not** tri-state) |
| `M1.m1_trigger/m1_retest` | M1 micro-confirmation at `time<=decision_time` | `m1_trigger` bool + `m1_retest` state one-hot |
| `permissions.allow_long/allow_short` | `ContextConstraints.allow_long/allow_short` (bool \| None) | **tri-state → 3 one-hot columns each** (see §3.3) |
| `lineage.depth/count` | `Episode.lineage` map size + component chain depth | numeric (count of non-NONE refs) |
| `reason_codes.<CODE>` | `FunnelRecord.reason` (REASONS list) | one-hot over REASONS + `""`(accepted) |

All categorical → one-hot; all cardinal (`direction`, `sequence_depth`, zone counts/proximity, lineage depth/count) → numeric. No future bar enters any field (`_validate_feature_value`-style scan re-implemented in v2 materializer, §4).

### 3.3 Tri-state permissions encoding (MANDATORY safe pattern, spec §3)

`allow_long` / `allow_short` carry **three** semantic states. The safe pattern creates **exactly three one-hot columns per feature** and holds the invariant at every hop:

```
allow_long_allow       = 1 iff allow_long is True
allow_long_block       = 1 iff allow_long is False
allow_long_no_opinion  = 1 iff allow_long is None   (the NULL third state)
allow_short_allow      = 1 iff allow_short is True
allow_short_block      = 1 iff allow_short is False
allow_short_no_opinion = 1 iff allow_short is None
```

The three columns for each feature **must sum to 1**. The materializer (`ai_outcome_v2_dataset.py`) and the trainer (`outcome_classifier` v2 vector builder) both enforce `sum == 1` and reject any row where `sum != 1` (raised as `EventError("TRI_STATE_COLLAPSED")`).

> **Scope of the `sum==1` guard (corrected):** the `sum==1` check is a **well-formedness invariant that catches missing/dropped/duplicated columns** (e.g., an encoder that fails to emit one of the three one-hot columns). It does **NOT** catch a `bool(None)->False` collapse: `None->False` would yield `allow=0, block=1, no_opinion=0`, which **still sums to 1** and would pass. Therefore the `sum==1` guard alone is NOT an anti-collapse guard. The REAL anti-collapse protection is the functional test **`test_v2_tristate_null_survives_chain`** (snapshot → funnel → dataset → trainer) which asserts that a NULL permission survives the entire chain as `no_opinion=1, allow=0, block=0` and is never turned into `False`/`block`. It is a MANDATORY test (gate G6). The `sum==1` guard remains a secondary structural check but must not be described as proof against `bool(None)->False`.

**Explicit traps to avoid (must not appear in v2):**
- `outcome_classifier.py:139` `1.0 if bool(ict.get(name, False)) else 0.0` — collapses three-state to two **only if applied to a tri-state field**. v2 never routes `allow_long/allow_short` through the intraday `flag()`; it runs through its own tri-state encoder.
- `engine/plan.py:68` `bos_real.fillna(False).astype(bool)` — never used in v2; BOS-optional fields are encoded as explicit 2-state bools *and are distinct from tri-state permission fields*. tri-state applies **only** to `allow_long/allow_short`.
- `wyckoff_intraday_diagnostic_train.py:112-117` `bool(row.get(..., False))` — never used in v2; the v2 trainer uses the tri-state encoder, not `bool(...)`.

**NULL NEVER bool(None)→False**: the serializer must emit the raw `True/False/None` tri-state verbatim into `features_at_t.permissions` and independently materialize the 6 one-hot columns from that verbatim source **using explicit `is True` / `is False` / `is None` comparisons — never truthiness** (see flat-column mapping, §6). The `from_dict`/trainer path reads ONLY the 6 flat columns with the `sum==1` well-formedness guard, and the null-preservation is verified end-to-end by the mandatory functional test `test_v2_tristate_null_survives_chain` (G6).

### 3.4 Funnel reason codes

`reason_codes` one-hot over `episodes.REASONS` (MISSING_SNAPSHOT, MISSING_IDENTITY, MISSING_REQUIRED_COMPONENT, OUT_OF_CONTEXT, SETUP_BLOCKED, SETUP_SUPERSEDED, INVALID_AUTHORITY, TEMPORAL_ORDER, FUTURE_DATA, MISSING_LINEAGE, INVALID_LINEAGE, DUPLICATE_EVENT, DUPLICATE_SETUP, CONFIG_MISMATCH) plus a dedicated `reason_codes=ACCEPTED` marker. Every rejected candidate's `reason` lands here (gate G7).

---

## 4. Dataset v2 Schema (`ai_outcome_v2_dataset.py`)

Each JSONL row is exactly:

```json
{
  "episode_id": "string",
  "event_time": "ISO-8601 UTC",
  "label_available_time": "ISO-8601 UTC (> event_time)",
  "label_end_12": "continuation|reversal|failure",
  "can_trade": false,
  "direction": -1|0|1,
  "sequence_depth": int,
  "features_at_t": { ... }    // v2 payload from §3
}
```

The materializer reuses the `diagnostic_training.load_causal_jsonl` **discipline** (same hash contracts) and adds v2-specific checks:

- **raw_sha256** = sha256 of the canonical JSONL bytes.
- **schema_hash** = sha256 of `{"format":"jsonl","columns":sorted(top-level keys + nested feature keys)}`.
- **source_name** = funnel artifact path basename.
- **strict-increasing event_time**: rows sorted by `event_time` (tie-break by canonical JSON); `current > prior` required (reuse `diagnostic_training._build_split` style). Duplicate `episode_id` rejected.
- **future-feature scan**: `_validate_feature_value(features_at_t, event_time, ...)` re-implemented to reject any nested key matching `_FORBIDDEN_FEATURE_PARTS` and any time-like field `> decision_time` (mirrors `ai_outcome_dataset._validate_feature_value` + `diagnostic_training._validate_feature_value`).
- **forbidden-field whitelist scan (G9)**: reject any candidate feature whose name matches `invalidated_bar|exit_price|MFE|MAE|hit_tp|hit_sl|pnl|profit|return|bars_held|result|label_*|outcome_*` — nonzero exit on any hit.
- **tri-state guard**: for `allow_long`/`allow_short`, verify the 6 one-hot columns sum to 1 per feature; reject `TRI_STATE_COLLAPSED` otherwise.
- **split** field NOT written by the materializer — the split is derived chronologically by `diagnostic_training` (60/20/20) at training time, which is the existing DIAGNOSTIC_ONLY contract. (v1's `build_snapshot_manifest`/preregistered splits are out of scope; this run is DIAGNOSTIC_ONLY and does not produce a certified snapshot.)

**Audit dataset (spec G7):** rejected/superseded candidates are written to a **separate** `ai_outcome_v2_audit.jsonl` with the same row shape (minus a real label: `label_end_12` is present only for accepted rows; for rejected rows a sentinel `null` label + `reason_codes` is emitted, and the file is excluded from training). Both manifests (train dataset + audit) record `raw_sha256`, `schema_hash`, `row_count`, `reason_counts`, `funnel_checksum`.

### 4.1 CRITICAL compatibility — v2 rows must pass `load_causal_jsonl` (Finding 1)

`runtime/ai_learning/diagnostic_training.py:189-203` (`load_causal_jsonl`) requires `features_at_t.context_inputs` (Mapping) with `sequence_direction, d1_bias, h4_location, h1_alignment` AND `features_at_t.sequence` (list); otherwise it raises "features_at_t causal incompleto". `run_diagnostic_training` (:422) calls `load_causal_jsonl` unconditionally, so every v2 row must satisfy this gate or the whole training run is blocked.

**Decision: Option A — relax `load_causal_jsonl` validation to accept v2 rows (backwards-compatible for v1 rows).** Not Option B (materializer emitting legacy blocks): dual-emitting both a v2 payload and legacy `context_inputs`/`sequence` is redundant, invites divergence between the two representations (a provenance leak surface), and forces fake values (e.g., a synthetic `d1_bias`) that undermine the anti-leakage G8/G9 story. Option A keeps ONE authoritative payload and makes the validation schema-aware.

**Exact code change in `runtime/ai_learning/diagnostic_training.py`:** replace the hardcoded intraday-required keys block (lines ~192-203) with a schema-versioned selection. Keep the existing strict logic for v1 rows unchanged (default `schema_group="intraday_v1"`), and add:

```python
# diagnostic_training.py — load_causal_jsonl, features_at_t branch
features = row.get("features_at_t")
if not isinstance(features, Mapping):
    raise DiagnosticTrainingError("fila %d: features_at_t requerido" % number)
schema_group = features.get("schema_group", "intraday_v1")

if schema_group == "intraday_v1":
    context = features.get("context_inputs")
    sequence = features.get("sequence")
    if not isinstance(context, Mapping) or not isinstance(sequence, (list, tuple)):
        raise DiagnosticTrainingError("fila %d: features_at_t causal incompleto" % number)
    required_context = {"sequence_direction", "d1_bias", "h4_location", "h1_alignment"}
    missing = sorted(required_context.difference(context))
    if missing:
        raise DiagnosticTrainingError("fila %d: faltan context_inputs: %s" % (number, ",".join(missing)))
elif schema_group == "engine_v2":
    # v2 payload (ai_outcome_v2) is validated by the materializer's own
    # future-feature + forbidden-field + tri-state scans (§4). Here we only
    # require the top-level v2 identity/guard fields so the row can be
    # consumed by the DIAGNOSTIC_ONLY trainer.
    required_v2 = {"context_state", "zones", "lifecycle", "M5", "M1",
                    "permissions", "lineage", "reason_codes"}
    missing = sorted(required_v2.difference(features))
    if missing:
        raise DiagnosticTrainingError("fila %d: features_at_t engine_v2 incompleto: %s" % (number, ",".join(missing)))
else:
    raise DiagnosticTrainingError("fila %d: schema_group desconocido: %s" % (number, schema_group))
```

Backwards compatibility is preserved: any v1 row without `schema_group` defaults to `intraday_v1` and keeps the original checks verbatim, so existing v1 datasets and all current `test_ai_outcome_diagnostic_train.py`/`test_ai_learning_outcome_classifier.py` tests pass unchanged. The v2 materializer sets `schema_group="engine_v2"` in every `features_at_t` root.

**New test:** `tests/test_ai_outcome_v2_schema.py::test_v2_rows_pass_load_causal_jsonl` — feed a v2-shaped row through `load_causal_jsonl` and assert it loads (no "causal incompleto" raised); assert a v1-shaped row still loads (backwards-compat); assert a row with neither schema_group nor the v2 keys raises.

---

## 5. Feature Set Registry (`runtime/ai_learning/outcome_classifier.py`)

### Decision: SEPARATE v2 registry (new keys) rather than extending `INTRADAY_FEATURE_PROFILES`

- **Choice**: add a sibling `V2_FEATURE_PROFILES` dict (name → exact feature-name tuple) plus a new `_v2_features(row, feature_names)` vector builder, and extend `_features` dispatch to route v2 tuples to it. Existing `INTRADAY_FEATURE_PROFILES`/`INTRADAY_*`/`FEATURE_NAMES` remain **byte-identical**.
- **Alternatives considered**:
  1. *Extend `INTRADAY_FEATURE_PROFILES` with B–F tuples.* Rejected: it would entangle v2 tri-state/HTF-zone features with the intraday Wyckoff/ICT path; `_intraday_features` would require invasive conditional logic that risks the v1 byte-identical invariant; `from_dict`/`train_outcome_classifier` profile checks enumerate `INTRADAY_FEATURE_PROFILES.values()`, so adding there changes dispatch semantics.
  2. *Add tuples to `INTRADAY_FEATURE_NAMES`.* Rejected: breaks `A (baseline replica)` — A must equal the exact 48-feature `INTRADAY_FEATURE_NAMES` tuple for comparison, and mutating it would invalidate baseline artifacts.
- **Rationale**: a separate registry isolates new behavior, keeps v1 byte-for-byte, and keeps `from_dict`'s profile-membership check simple to extend. Profile names use a `V2_` prefix to guarantee no collision with `FEATURE_NAMES`/`INTRADAY_*`.

### 5.1 New constants and exact feature-name tuples

```python
# CARDINAL (numeric) — shared, no one-hot
V2_CARDINAL = ("direction", "sequence_depth",
               "zone_poi_count", "zone_bsl_count", "zone_ssl_count",
               "zone_proximity", "lineage_depth", "lineage_count")

# A == baseline replica (must equal INTRADAY_FEATURE_NAMES exactly)
V2_A = INTRADAY_FEATURE_NAMES            # 48 features, unchanged

# B = A + context_state + direction_hint + regime_stack
#   context_state one-hot: 3 layers x (OK,INCOMPLETE,BLOCKED) = 9
#   direction_hint one-hot: 4
#   regime_stack one-hot:   3 layers x 7 regimes = 21
V2_B_ADD = ("context_d1=OK", "context_d1=INCOMPLETE", "context_d1=BLOCKED",
            "context_h4=OK", "context_h4=INCOMPLETE", "context_h4=BLOCKED",
            "context_h1=OK", "context_h1=INCOMPLETE", "context_h1=BLOCKED",
            "direction_hint=BULLISH", "direction_hint=BEARISH",
            "direction_hint=MIXED", "direction_hint=UNKNOWN",
            "regime_d1=TREND_BULL", "regime_d1=TREND_BEAR", "regime_d1=RANGE",
            "regime_d1=EXPANSION", "regime_d1=RETRACEMENT",
            "regime_d1=COMPRESSION", "regime_d1=UNKNOWN",
            "regime_h4=TREND_BULL", "regime_h4=TREND_BEAR", "regime_h4=RANGE",
            "regime_h4=EXPANSION", "regime_h4=RETRACEMENT",
            "regime_h4=COMPRESSION", "regime_h4=UNKNOWN",
            "regime_h1=TREND_BULL", "regime_h1=TREND_BEAR", "regime_h1=RANGE",
            "regime_h1=EXPANSION", "regime_h1=RETRACEMENT",
            "regime_h1=COMPRESSION", "regime_h1=UNKNOWN")

# C = B + BOS HTF layer bools + zones + lifecycle
#   BOS HTF: 3 layers x 2 bools (bullish/bearish) = 6
#   zones: cardinal counts/proximity already in V2_CARDINAL (adds the numeric)
#   lifecycle one-hot: SETUP/ELIGIBLE/BLOCKED/SUPERSEDED/OUT_OF_CONTEXT = 5
V2_C_ADD = ("bos_d1_bullish", "bos_d1_bearish",
            "bos_h4_bullish", "bos_h4_bearish",
            "bos_h1_bullish", "bos_h1_bearish",
            "lifecycle=SETUP", "lifecycle=ELIGIBLE", "lifecycle=BLOCKED",
            "lifecycle=SUPERSEDED", "lifecycle=OUT_OF_CONTEXT")

# D = C + M5 micro (m5_bos, m5_displacement, m5_fvg bools)
V2_D_ADD = ("m5_bos_bullish", "m5_bos_bearish",
            "m5_displacement_bullish", "m5_displacement_bearish",
            "m5_fvg_bullish", "m5_fvg_bearish")

# E = D + M1 micro (m1_trigger bool + m1_retest one-hot)
V2_E_ADD = ("m1_trigger_bullish", "m1_trigger_bearish",
            "m1_retest=RETEST", "m1_retest=NO_RETEST", "m1_retest=UNKNOWN")

# F = E + permissions tri-state + lineage + reason_codes
#   permissions: 6 one-hot columns (allow_long/allow_short x 3)
#   lineage: cardinal depth/count already above
#   reason_codes one-hot: REASONS(14) + ACCEPTED = 15
V2_F_ADD = ("allow_long_allow", "allow_long_block", "allow_long_no_opinion",
            "allow_short_allow", "allow_short_block", "allow_short_no_opinion",
            *(f"reason_{code}" for code in REASONS_V2), "reason_ACCEPTED")
```

The **V2 registry** is built by prefix-composition (each set = previous set + its additions). The adapter/materializer emit the full v2 payload; `_v2_features` selects the columns for the requested `feature_names` tuple, so A→F share one materialization and differ only in the selected column list. This guarantees **equality of experiment** (same corpus, same rows, same seed/split/procedure) across A–F (spec §7) — only the feature windowed differs.

### 5.2 Dispatch update in `_features` and `from_dict`/`train`

```python
# in outcome_classifier.py
V2_FEATURE_PROFILES = {  # name -> tuple, prefix-composed
    "V2_A": V2_A, "V2_B": V2_B, "V2_C": V2_C, "V2_D": V2_D,
    "V2_E": V2_E, "V2_F": V2_F,
}
_V2_FEATURE_TUPLES = tuple(V2_FEATURE_PROFILES.values())

def _features(row, feature_names=FEATURE_NAMES):
    if tuple(feature_names) in INTRADAY_FEATURE_PROFILES.values():
        return _intraday_features(row, feature_names)
    if tuple(feature_names) in _V2_FEATURE_TUPLES:
        return _v2_features(row, feature_names)
    # ... existing non-intraday path unchanged
```

`from_dict` (line 317) extends its membership check: `... and feature_names != FEATURE_NAMES and feature_names not in _V2_FEATURE_TUPLES` → raise if unregistered. `train_outcome_classifier` (line 460) likewise accepts `(FEATURE_NAMES, *INTRADAY_FEATURE_PROFILES.values(), *_V2_FEATURE_TUPLES)`. `_v2_features` also enforces the trio `sum==1` guard and dimension/finiteness checks (mirroring `_intraday_features`' final validation).

### 5.3 CRITICAL — how the 48 A-features are computed from a v2 row (Finding 2)

**Dispatch is v2-first for ALL v2 tuples, including V2_A.** `_features` routes every tuple in `_V2_FEATURE_TUPLES` (A–F) to `_v2_features`, **never** through `_intraday_features`. Therefore V2_A does not read the legacy `context_inputs`/`intraday`/`sequence` blocks — those are not emitted (Finding 1 Option A). Instead the v2 payload carries a **v2-native intraday source block**, populated causally by the adapter, and `_v2_features` maps it onto the 48 `INTRADAY_FEATURE_NAMES`.

**v2-native source block (per row) — `features_at_t["intraday_v2"]`:** the adapter extracts the same causal M15/H1 Wyckoff + ICT M15 state the baseline computes per decision-time M15 bar (identical `build_features`/`build_wyckoff_snapshot` inputs, evaluated at `time <= decision_time`), stored under v2 namespacing — NOT under `context_inputs`/`intraday`:

```json
"features_at_t": {
  "schema_group": "engine_v2",
  "direction": -1|0|1,
  "sequence_depth": int,
  "intraday_v2": {
    "ict_m15": { "ict_m15_fvg_bullish": bool, "ict_m15_fvg_bearish": bool,
                 "ict_m15_ob_bullish": bool, "ict_m15_ob_bearish": bool, ... },
    "wyckoff": { "H1": { "phase": "..." , "phase_progress": float, "events": [ ... ] },
                 "M15": { "phase": "...", "phase_progress": float, "events": [ ... ] } }
  },
  ...
}
```

**`_v2_features` A-mapping (exact per-column rule):** for each A column name in `INTRADAY_FEATURE_NAMES`, `_v2_features` resolves the value from `intraday_v2` using the SAME formula `_intraday_features` uses, but reading the v2 block. Concretely:
- `direction`/`sequence_depth` → top-level `features_at_t["direction"]` / `["sequence_depth"]` (v2-native top-level, identical semantics to baseline `sequence_direction`/`sequence_depth`).
- all `ict_m15_*` columns → `intraday_v2["ict_m15"][<column>]` via the boolean `flag()` semantics — a bool is required; the column name maps 1:1 to the `ict_m15` key (e.g. `ict_m15_fvg_bullish` → `intraday_v2["ict_m15"]["ict_m15_fvg_bullish"]`).
- all `wyckoff_*` H1/M15 columns → `intraday_v2["wyckoff"]["H1"|"M15"]` phase/event booleans, computed with the same predicates as `_intraday_features`'s Wyckoff branch (phase==target → 1.0; event membership → 1.0).

This keeps A **numerically identical** to `_intraday_features` output *for the same causal M15/H1 window* while reading from the v2 block.

**Parity test (mandatory, gate G6):** `tests/test_ai_outcome_v2_tristate.py::test_v2_A_parity_with_baseline_intraday` — take a set of real M15 events; produce the A-vector through BOTH (a) the baseline `_intraday_features` on a v1-shaped row, and (b) `_v2_features(V2_A)` on a v2 row with the identical causal M15/H1 window; assert element-wise equality within `atol=1e-9`. This proves the v2 path reproduces the 48-feature baseline on the same events and that the dispatch never reintroduces a value drift.

### 5.4 Flat-column encoding — exact derivation for EVERY registry column (Finding 4)

Every flat column in sets A–F is derived from the nested `features_at_t` payload with **explicit identity comparisons (`is True` / `is False` / `is None`) — never truthiness**. Cardinal columns are numeric passthroughs. One-hot columns are binary flags where exactly one member equals 1.

**Cardinal (numeric passthrough, no one-hot):**

| Column (A–F) | Source path in `features_at_t` | Rule |
| --- | --- | --- |
| `direction` | `["direction"]` | `int` passthrough (−1/0/1) |
| `sequence_depth` | `["sequence_depth"]` | `int` passthrough (≥0) |
| `zone_poi_count` | `["zones"]["poi"]["count"]` | `int` passthrough, else `0` |
| `zone_bsl_count` | `["zones"]["bsl"]["count"]` | `int` passthrough, else `0` |
| `zone_ssl_count` | `["zones"]["ssl"]["count"]` | `int` passthrough, else `0` |
| `zone_proximity` | `["zones"]["proximity"]` | `float` passthrough, else `0.0` |
| `lineage_depth` | `["lineage"]["depth"]` | `int` passthrough, else `0` |
| `lineage_count` | `["lineage"]["count"]` | `int` passthrough, else `0` |

**A-features (from `["intraday_v2"]`, see §5.3):** each `ict_m15_*` → `["intraday_v2"]["ict_m15"][<col>]`, `1.0 if v is True else 0.0` (v MUST be a bool present in the block; absent → rejected by schema, not defaulted). Each `wyckoff_*` → `["intraday_v2"]["wyckoff"]["H1"|"M15"]` phase/event predicate (as §5.3). No truthiness of `None`.

**B one-hot / binary blocks:**

| Column | Source path | Rule |
| --- | --- | --- |
| `context_state=TARGET` | `["context_state"]` | `1 = 1 if payload["context_state"] == "TARGET" else 0` (an enum; exact string equality, not truthiness) |
| `context_state=NEUTRAL` | `["context_state"]` | `1 if == "NEUTRAL" else 0` |
| `context_state=AVOID` | `["context_state"]` | `1 if == "AVOID" else 0` |
| `direction_hint=BULLISH` | `["context_constraints"]["direction_hint"]` | `1 if == "BULLISH" else 0` (ditto BEARISH/MIXED/UNKNOWN) |
| `regime_d1=TREND_BULL` (etc.) | `["context_constraints"]["regime_stack"]["D1"]` | `1 if == value else 0` for each regime enum; same for `H4`, `H1` |

**C one-hot / binary blocks:**

| Column | Source path | Rule |
| --- | --- | --- |
| `bos_d1_bullish` | `["bos_htf"]["D1"]["bullish"]` | `1.0 if v is True else 0.0`; same with `bearish` (v is `bool|None`; None → both 0, an explicit 2-state optional, NOT `bool(None)`); nested keys `["H4"]`, `["H1"]` analogously |
| `zone_*` | cardinal (above) | — |
| `lifecycle=SETUP` (etc.) | `["lifecycle"]` | `1 if == "SETUP" else 0` for each of the 5 lifecycle enums (exact string equality) |

**D one-hot / binary blocks:**

| Column | Source path | Rule |
| --- | --- | --- |
| `m5_bos_bullish` | `["M5"]["bos"]["bullish"]` | `1.0 if v is True else 0.0`; `m5_bos_bearish` same on `["M5"]["bos"]["bearish"]` |
| `m5_displacement_bullish` | `["M5"]["displacement"]["bullish"]` | `1.0 if v is True else 0.0`; bearish analogously |
| `m5_fvg_bullish` | `["M5"]["fvg"]["bullish"]` | `1.0 if v is True else 0.0`; bearish analogously |

**E one-hot / binary blocks:**

| Column | Source path | Rule |
| --- | --- | --- |
| `m1_trigger_bullish` | `["M1"]["trigger"]["bullish"]` | `1.0 if v is True else 0.0`; bearish analogously |
| `m1_retest=RETEST` | `["M1"]["retest"]` | `1 if == "RETEST" else 0`; `NO_RETEST`/`UNKNOWN` analogously (enum) |

**F one-hot blocks:**

| Column | Source path | Rule |
| --- | --- | --- |
| `allow_long_allow` | `["permissions"]["allow_long"]` | `1 if v is True else 0` |
| `allow_long_block` | `["permissions"]["allow_long"]` | `1 if v is False else 0` |
| `allow_long_no_opinion` | `["permissions"]["allow_long"]` | `1 if v is None else 0` |
| `allow_short_allow` | `["permissions"]["allow_short"]` | `1 if v is True else 0` |
| `allow_short_block` | `["permissions"]["allow_short"]` | `1 if v is False else 0` |
| `allow_short_no_opinion` | `["permissions"]["allow_short"]` | `1 if v is None else 0` |
| `reason_<CODE>` | `["reason_codes"]` | `1 if <CODE> in payload["reason_codes"] else 0` (list membership) |
| `reason_ACCEPTED` | `["reason_codes"]` | `1 if "ACCEPTED" in payload["reason_codes"] else 0` |

**Enforcement:** `_v2_features` applies these rules verbatim (single canonical encoder). The materializer writes raw v2 payload; the encoder is the ONLY place columns are flattened, so the mapping table above is the single source of truth. A column whose source path is absent in the payload is a **schema violation** (rejected), except `0`/`0.0` only where explicitly allowed above (zone/lineage counts, wym optional BOS/M5/M1 bools that are 2-state, never tri-state).

### 5.5 Pinned frames source & FULL-vs-PREFIX computation (Finding 5, RESOLVED)

**Canonical frames (pin):** `data/raw/EURUSD/*.parquet` — the exact files consumed by the operational engine `/` navigator:

```
data/raw/EURUSD/EURUSD_M1.parquet
data/raw/EURUSD/EURUSD_M5.parquet
data/raw/EURUSD/EURUSD_M15.parquet
data/raw/EURUSD/EURUSD_H1.parquet
data/raw/EURUSD/EURUSD_H4.parquet
data/raw/EURUSD/EURUSD_D1.parquet
```

Columns `time/open/high/low/close`, loaded via `engine.data_feed.load_frames("EURUSD", (M1,M5,M15,H1,H4,D1), data_dir=ROOT/"data"/"raw"/"EURUSD")` (equivalently `engine.market_features.load_frames`). **No MT5, no live feed** — these are the frozen local parquet frames the funnel and navigator already run on. (M3 parquet exists but is not needed for V2_A–F.)

**Provenance chain (raw → pinned parquet):** the upstream raw source is the monthly Dukascopy CSVs under `datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/<year>/eurusd-m15-bid-*.csv` (and the sibling raw dirs for other TFs). The `.parquet` files are produced from those CSVs by a **deterministic, byte-stable build** (existing `run_ict_2006_*` pipeline reference the same `raw_monthly/2006` source). The design pins the **parquet bytes**, not the CSVs, because that is what the navigator/materializer actually reads.

**sha256 pinning strategy (byte-identical reruns, G0/G7/G11):** stream-hash each parquet file's bytes using the exact `_source_artifacts` routine in `engine/mt5_operational_snapshot.py:58-77` (1 MiB chunked `hashlib.sha256` over `path.open("rb")`), producing per-TF `{tf, path, bytes, sha256}`. The combined frames fingerprint is `sha256("\n".join(sorted(f"{tf}|{path}|{bytes}|{sha256}" for each artifact)))` — mirroring `mtf_replay_t7.py:112` / `mtf_replay_t7f.py:50` lifting-set encoding. The v2 manifest MUST record `frames_sha256` (combined) and each per-file `sha256`, and `ai_outcome_v2_dataset` must FAIL G7/G11 if any file hash differs between extraction and rerun (re-hash → compare → fail, never silently reuse).

**FULL vs PREFIX (causal window, G4/G5/G8):**
- **FULL** = the whole frame as loaded (all bars, including any bar with `time > decision_time`).
- **PREFIX** = `frame[time <= decision_time]`, computed by the exact `_frame_prefix(frame, decision_time)` function in `engine/mt5_operational_snapshot.py:47-55` (converts `time` to UTC, drops NaT, sorts, keeps rows with `time <= decision_time`).

The navigator re-invocation AND the adapter's intraday_v2 extraction MUST use the **PREFIX** window (forward-PIT, `time <= decision_time`); the **FULL** window is used ONLY by the causal-horizon test `test_v2_full_vs_prefix_identical` (G8) which asserts PREFIX-derived features == FULL-derived features at the *decision* index (i.e., no future data leaks: features derived from bars after decision_time must not exist in the PREFIX feature matrix). This is exactly the existing FULL-vs-PREFIX discipline in the engine and Dukascopy audit scripts (`mtf_replay_t7*`).

**Every rerun** re-reads the same pinned parquet paths and re-hashes them; because parquet bytes are frozen and the PREFIX computation is deterministic, the feature matrix and dataset sha256 are byte-identical across reruns (reproducibility G11).

---

## 6. Compatibility Plan

- **v1 untouched**: `INTRADAY_FEATURE_PROFILES` values, `FEATURE_NAMES`, `_intraday_features`, `_features` intraday branch, and `from_dict`/`train` validation for existing profiles are unchanged. Baseline artifacts remain byte-identical.
- **No name collision**: all v2 column names use `context_*`, `direction_hint=*`, `regime_*`, `bos_*`, `zone_*`, `lifecycle=*`, `m5_*`, `m1_*`, `allow_*`, `reason_*` — none overlap `FEATURE_NAMES` or `INTRADAY_*`. Registry keys use `V2_` prefix.
- **Dispatch isolation**: v2 tuples route to `_v2_features`, never through `_intraday_features`. Existing tests (`test_ai_learning_outcome_classifier.py`) keep passing unchanged.
- **Existing script imports**: `diagnostic_training` is extended only by accepting `_V2_FEATURE_TUPLES` in its profile check (additive); `run_diagnostic_training` and `load_causal_jsonl` signatures unchanged.

---

## 7. Runner Design

### 7.1 `ai_outcome_v2_dataset.py` (materializer)

CLI: `python scripts/lab/experiments/ai_outcome_v2_dataset.py --funnel <path> --frames <dir> --output-jsonl <path> --output-audit <path> --manifests <path>`.

Produces `.jsonl` + `.audit.jsonl` + a manifest JSON recording: `raw_sha256`, `schema_hash`, `row_count`, `reason_counts`, `funnel_checksum`, `forbidden_field_scan={hits:0}`, `tri_state_guard={collapses:0}`, `generator_evidence` (commit/branch/worktree). Nonzero exit on any future-feature hit, any forbidden-field hit, or any tri-state collapse.

### 7.2 `ai_outcome_v2_ablation.py`

Running A–F under **equality of experiment** (spec §7): same corpus, dates, target `label_end_12`, seed `20260831`, hyperparameters (`deterministic_multinomial_softmax`, lr=0.05, l2=0.0001, 500 iters), chronological 60/20/20 split. For each set F→A (descending), call `run_diagnostic_training(jsonl, target="label_end_12", seed=20260831, feature_names=set_tuple)`. Emit a table `A→F` with per-set: N, feature count, train/validation/test_oos metrics (acc/log_loss), and the **predecessor delta** (B vs A, C vs B, …). No TEST_OOS tuning; no circular optimization.

### 7.3 `ai_outcome_v2_eval.py`

Given the six `OutcomeClassifierArtifact`s and the same v2 test rows, compute on **TEST_OOS only** (spec §8):
- accuracy, log_loss, **Brier**, per-class precision/recall/F1, **ROC-AUC** & **PR-AUC** (one-vs-rest), full 3×3 confusion matrix.
- **Calibration**: calibration curve + **ECE**.
- **Per-segment tables** (only cells with N ≥ 30): per-year, per-context-state, per-permission, per-zone-type, per-setup-eligibility, per-regime.
- **Comparison vs baseline** fixed table (spec §8: population, N, features, causality G8, leakage G9, OOS stability, calibration, performance, coverage, complexity, reproducibility G11).
- **Final classification** into exactly one of: `CERTIFIED_IMPROVEMENT` / `NO_MEASURABLE_IMPROVEMENT` / `INSUFFICIENT_EVIDENCE` / `FAILED_CAUSALITY` / `FAILED_PROVENANCE` / `FAILED_REPRODUCIBILITY`, per the decision rule (H1 requires log_loss ↓≥0.02 AND/OR acc ↑≥1pp on TEST_OOS, confirmed by calibration + per-segment).
- **Sample-size guard**: any cell with N < 30 is not reported (flagged `insufficient_n`).

---

## 8. Test Plan (design-level)

New tests under `tests/` (no existing test modified unless it asserts profile enumeration — verify; additively extend only):

| Test | Path | Gate |
|---|---|---|
| Tri-state NULL survives snapshot→funnel→dataset→trainer (NULL stays NO_OPINION, never False) | `tests/test_ai_outcome_v2_tristate.py::test_v2_tristate_null_survives_chain` | G6 |
| Tri-state collapse rejected at materialize + trainer (`sum!=1` → `TRI_STATE_COLLAPSED`) | `tests/test_ai_outcome_v2_tristate.py::test_v2_tristate_collapse_rejected` | G6 |
| NULL `bool(None)→False` trap never applied (assert no `fillna(False)`/`bool(x,False)` on permissions) | `tests/test_ai_outcome_v2_tristate.py::test_v2_no_none_false_collapse` | G6 |
| Causal horizon FULL-vs-PREFIX produce identical feature matrices (extract at `<=event_time` vs full window) | `tests/test_ai_outcome_v2_causality.py::test_v2_full_vs_prefix_identical` | G8 |
| Forbidden-field leakage scan rejects any hit (invalidated_bar/exit/MFE/MAE/hit_tp/pnl/.../label_*/outcome_*) | `tests/test_ai_outcome_v2_causality.py::test_v2_forbidden_field_scan` | G9 |
| Future-feature (time > event_time) rejected | `tests/test_ai_outcome_v2_causality.py::test_v2_future_feature_rejected` | G8/G9 |
| Strict-increasing event_time + duplicate episode_id rejected | `tests/test_ai_outcome_v2_schema.py::test_v2_event_time_and_identity` | G1/G10 |
| raw_sha256 / schema_hash deterministic and recorded | `tests/test_ai_outcome_v2_schema.py::test_v2_hashes_and_manifest` | G1 |
| Temporal split chronological, no random; TRAIN/VALIDATION/TEST_OOS boundaries | `tests/test_ai_outcome_v2_schema.py::test_v2_temporal_splits` | G10 |
| Reproducibility: same seed/data → identical artifacts | `tests/test_ai_outcome_v2_repro.py::test_v2_reproducible` | G11 |
| v1 pipeline untouched: `INTRADAY_*`/`FEATURE_NAMES` tuples byte-identical; v2 tuples don't collide; existing intraday test still passes | `tests/test_ai_learning_outcome_classifier.py` (add `test_v2_registry_no_collision`) | — (compat) |
| Adapter funnel reproduction (funnel row count == adapted row count; per-reason counts) | `tests/test_ai_outcome_v2_adapter.py::test_v2_funnel_reproduction` | G7 |
| `from_dict` accepts/validates a V2_F profile (membership + mean/scale/weights dimension) | `tests/test_ai_learning_outcome_classifier.py::test_v2_artifact_validates_profile` | — |
| v2 rows pass `load_causal_jsonl` (`schema_group="engine_v2"` loads; v1 intraday rows still load; missing-keys row rejected) — Finding 1 | `tests/test_ai_outcome_v2_schema.py::test_v2_rows_pass_load_causal_jsonl` | G0/G10 |
| A-vector parity: v2 path (`_v2_features(V2_A)`) == baseline `_intraday_features` on same events, `atol=1e-9` — Finding 2 | `tests/test_ai_outcome_v2_tristate.py::test_v2_A_parity_with_baseline_intraday` | G6 |

---

## 9. Gates Wiring (G0–G13 → automated check / evidence artifact)

| Gate | Check | Evidence / automated check |
|---|---|---|
| G0 | Provenance documented & auditable | `ai_outcome_v2_dataset` manifest: `source_artifacts` (funnel path+sha, frames sha, adapter commit), `funnel_checksum`, provenance block |
| G1 | Snapshot hash/schema_version/row count | manifest `raw_sha256`, `schema_hash`, `row_count` + `test_v2_hashes_and_manifest` |
| G2 | Context NOT hardcoded; per-event extraction | `test_v2_full_vs_prefix_identical` + manifest spot-check N events `direction_hint != UNKNOWN` |
| G3 | Lifecycle per event | `lifecycle` column distribution report in manifest + `test_v2_funnel_reproduction` |
| G4 | M5 causal at decision_time only | FULL-vs-PREFIX diff == 0 (`test_v2_full_vs_prefix_identical`) |
| G5 | M1 causal at decision_time only | FULL-vs-PREFIX diff == 0 (same test) |
| G6 | NULL third state survives | `test_v2_tristate_null_survives_chain` (automated, mandatory) |
| G7 | Funnel rows == adapter output | `test_v2_funnel_reproduction` + manifest row/reason counts |
| G8 | FULL vs PREFIX causal window | `test_v2_full_vs_prefix_identical` |
| G9 | Forbidden-column whitelist scan | automated scan report (`hits=0`) + `test_v2_forbidden_field_scan` |
| G10 | Chronological, no random; 3 partitions | `test_v2_temporal_splits` + monotonic event_time check |
| G11 | Reproducible (seed/data/result) | `test_v2_reproducible` + stored train hash vs re-run |
| G12 | OOS eval only on TEST_OOS | `ai_outcome_v2_eval` manifest scoped to TEST_OOS; no VALIDATION/TRAIN in final table |
| G13 | Ablation vs predecessor; no circular opt | `ai_outcome_v2_ablation` A→F table (predecessor deltas), fixed hyperparameters |

Every gate has a **fail action**: root cause → fix → re-test → record (never silent continue), per spec §6.

---

## 10. Execution Order (for sdd-tasks)

1. **Registry + dispatch** (`outcome_classifier.py`): add `V2_*` constants, `V2_FEATURE_PROFILES`, `_v2_features`, extend `_features`/`from_dict`/`train` membership checks; add `REASONS_V2` import. No data flows yet.
2. **Adapter** (`ai_outcome_v2_adapter.py`): `adapt_funnel_artifact`, causal extraction, tri-state encoder, reason codes; unit tests.
3. **Materializer** (`ai_outcome_v2_dataset.py`): JSONL + audit dataset + hashes + scans + tri-state guard + manifest; tests (G1/G6/G7/G8/G9/G10).
4. **Wire the diagnostic path**: confirm `run_diagnostic_training` accepts `_V2_FEATURE_TUPLES` and produces v2 artifacts for A and F end-to-end; reproducibility test (G11).
5. **Ablation runner** (`ai_outcome_v2_ablation.py`): A→F under equality of experiment; G13 evidence.
6. **Eval runner** (`ai_outcome_v2_eval.py`): OOS metrics, calibration, per-segment (N≥30), baseline comparison, 6-category classification; G12 evidence.
7. **Gates evidence aggregation** + worklog + contract/SDD doc addenda + Engram persistence + local selective commit (no push).

---

## 11. Open Questions

- [ ] Confirm the funnel artifact on disk already contains the per-event `context_state`/constraints, or whether the adapter must re-invoke `MTFNavigator.navigate` per event (design assumes re-invocation, which is allowed as deterministic/PIT). Resolved at sdd-tasks step 2 against the real artifact schema.
- [x] **RESOLVED (Finding 5):** exact `frames` source pinned to `data/raw/EURUSD/EURUSD_{M1,M5,M15,H1,H4,D1}.parquet` via `engine.data_feed.load_frames`, with streaming `sha256` per `mt5_operational_snapshot._source_artifacts` and FULL-vs-PREFIX per `_frame_prefix` (§5.5). No MT5.

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `scripts/lab/experiments/ai_outcome_v2_adapter.py` | Create | Engine funnel → causal `features_at_t` (A–F payload, tri-state safe) |
| `scripts/lab/experiments/ai_outcome_v2_dataset.py` | Create | v2 materializer (dataset + audit + hashes + scans + tri-state guard) |
| `scripts/lab/experiments/ai_outcome_v2_ablation.py` | Create | A→F ablation under equality of experiment |
| `scripts/lab/experiments/ai_outcome_v2_eval.py` | Create | OOS metrics + per-segment + baseline comparison + classification |
| `runtime/ai_learning/outcome_classifier.py` | Modify | Add `V2_FEATURE_PROFILES`, `_v2_features`, dispatch + validation (additive) |
| `runtime/ai_learning/diagnostic_training.py` | Modify | Accept `_V2_FEATURE_TUPLES` in profile check; schema-versioned `load_causal_jsonl` relaxation for `schema_group="engine_v2"` (both additive, v1 byte-unchanged; §4.1) |
| `tests/test_ai_outcome_v2_*.py` (+ classifier) | Create | Test plan §8 |
| `docs/planificacion/SDD_AI_OUTCOME_CLASSIFIER_V1.md` | Modify | Add v2 section (section 5) |
| `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md` | Modify | Addendum: v2 target, feature sets, gates |
| `.hermes-worklog/` | Create | Mission log entries |

**NOT modified:** baseline artifacts, `backtest/replay.py`, `engine/` (read-only), any file that would break the v1 pipeline, no `openspec/`.

## Auditoría (R3 reliability audit — APPROVE_WITH_FIXES)

Independent reliability audit of the design returned **APPROVE_WITH_FIXES** with 2 CRITICAL + 3 WARNING findings. All five are resolved in this document as follows:

| # | Severity | Finding | Resolution (section) |
| --- | --- | --- | --- |
| 1 | CRITICAL | v2 rows must pass `load_causal_jsonl` (requires `context_inputs`+`sequence`) | **Option A**: schema-versioned relaxation of `load_causal_jsonl` (`schema_group="engine_v2"`), v1 rows byte-unchanged; exact patch + test in §4.1 |
| 2 | CRITICAL | V2_A must be computable from v2 payload (not via `_intraday_features` reading legacy blocks) | v2-first dispatch to `_v2_features` for ALL v2 tuples + v2-native `intraday_v2` source block + parity test in §5.3 |
| 3 | WARNING | `sum==1` guard does NOT catch `bool(None)->False` (claim was false) | Claim corrected in §3.3: `sum==1` is only a well-formedness invariant; the REAL anti-collapse guard is the mandatory functional test `test_v2_tristate_null_survives_chain` |
| 4 | WARNING | Flat-column encoding not specified | Full column→source-path→rule mapping table for EVERY column in A–F in §5.4 |
| 5 | WARNING | Frames source not pinned | Pinned `data/raw/EURUSD/*.parquet` + loader + sha256 strategy + FULL-vs-PREFIX in §5.5 |

FAIL-gate evidence note: this gate (design reliability) is recorded as resolved by the corrections immediately above; the design is now self-consistent with the engine's `load_causal_jsonl` contract, reproducible frames, and the tri-state test is the authoritative null-preservation guard.

---

## Key Risks

- **Dimension growth / class imbalance**: A→F adds up to ~70+ one-hot columns over the 48 baseline; with funnel gate reduction the effective N per segment may drop. Mitigated by equality-of-experiment corpus, N≥30 guard, and per-segment flagging rather than dropping cells.
- **Engine-funnel row reduction**: stricter funnel may yield far fewer accepted episodes than baseline 53,761. Accepted as quality-over-quantity (spec §1); eval reports `coverage`/abstention; some segments may fall below N≥30 (reported, not fabricated).
- **Provenance**: adapter recomputes context-state causally; frames source pinned (§5.5) with streaming sha256 + FULL-vs-PREFIX; manifest must bind `funnel_checksum` + `frames_sha256` so G0/G7/G11 are auditable and any rerun is byte-identical.
- **Tri-state regression**: any future edit re-introducing `bool(None)->False` would silently break G6. **Guard corrected (Finding 3):** the `sum==1` trainer check is only a well-formedness invariant and does NOT catch `None->False`; the authoritative guard is the mandated functional test `test_v2_tristate_null_survives_chain` (asserts NULL→NO_OPINION survives snapshot→funnel→dataset→trainer) plus the flat-column encoder's explicit `is None` comparisons (§5.4). Test is mandatory, not documentation-only.
