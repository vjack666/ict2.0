# Specification — AI Outcome Classifier v2 (Engine-Connected Retraining)

**Change:** ai-outcome-v2
**Date:** 2026-09-05
**Status:** SPEC (→ design)
**Proposal:** `.hermes/plans/2026-09-05_AI_OUTCOME_V2_PROPOSAL.md`
**Scope gate:** THIS SPEC ADDS NOTHING BEYOND THE PROPOSAL. No invented requirements, no scope creep.
**Baseline:** `wyckoff_intraday_2006_2010_train.json` + `.jsonl` (53,761 rows, 2006-01-02→2010-12-31), sha `7a6109…` — UNTOUCHED.
**Global constraints:** `can_trade=false`, no MT5, no `engine/` modification (read-only), no circular optimization, no git push, no `TRAINING_ELIGIBLE` / `edge` declaration (this run is `DIAGNOSTIC_ONLY`; provenance BLOCKED → gate TRAINING_ELIGIBLE is NOT achievable).

---

## 1. Source of truth — engine funnel adapter

The dataset SHALL be produced exclusively from `engine/episodes.py` (`build_episodes` → `Episode` + `FunnelRecord`). Consumption is READ-ONLY. **NOT** `backtest/replay.py`, NOT `mtf_replay`, NOT `engine/daily_motor`. Row counts may be smaller than baseline (stricter funnel) — quality over quantity is accepted.

The adapter (`scripts/lab/experiments/ai_outcome_v2_adapter.py`) SHALL traverse the funnel artifact `records`+`episodes`+`rejections`. Every `FunnelRecord` (ACCEPTED, REJECTED, SUPERSEDED) SHALL be materialized as a candidate row with its `reason` preserved — rejected candidates are NEVER silently dropped from the audit trail (G7, G8).

**Field mapping (authoritative):**

| Funnel source (`episodes.py`) | Dataset v2 feature |
|---|---|
| `Episode.decision_time` | `event_time` (identity) |
| `Episode.direction` | `direction` |
| `Episode.episode_id` / `canonical_setup_key` | `episode_id` |
| `Episode.status` + `reason` | `lifecycle` stage + `reason_codes` |
| `Episode.lineage` (context_htf/poi/refinement/confirmation/trigger ids) | `lineage` depth/count |
| `Episode.component_tfs` | `permissions`/zones provenance |
| `FunnelRecord.reason` (REASONS list incl. `MISSING_SNAPSHOT`…`MISSING_LINEAGE`) | `reason_codes` one-hot |

The context/lifecycle/permissions/zone/BOS/M5/M1/regime fields SHALL be sourced from a per-event causal extraction: the `ContextConstraints` payload (via `MTFNavigator`) observable at `time <= event_time` — `direction_hint`, `regime_stack` (RegimeLabel per layer), `allow_long`, `allow_short`, `location_zones` (Zone.kind POI/BSL/SSL/DEALING), `liquidity_targets`, and `LayerSnapshot` BOS/displacement/regime per layer.

---

## 2. Dataset v2 schema (`ai_outcome_dataset_v2.py`)

Each JSONL row SHALL be an object with EXACTLY these top-level fields:

| Field | Type | Cardinality | Rule |
|---|---|---|---|
| `episode_id` | string | 1 | funnel identity |
| `event_time` | ISO-8601 UTC | 1 | observation time |
| `label_available_time` | ISO-8601 UTC | 1 | MUST be > `event_time` |
| `label_end_12` | string | 1 | `continuation/reversal/failure` (Target, §4) |
| `can_trade` | bool | 1 | MUST be `false` |
| `direction` | int | 1 | -1/0/1 |
| `sequence_depth` | int | 1 | depth |
| `features_at_t` | object | 1 | sub-structure below |

`features_at_t` SHALL contain: `context_state` (direction_hint, location, regime_stack per layer, zone lists, BOS HTF bools per D1/H4/H1), `zones` (counts + proximity for POI/BSL/SSL), `lifecycle` (stage: SETUP/ELIGIBLE/BLOCKED/SUPERSEDED/OUT_OF_CONTEXT), `M5` (m5_bos, m5_displacement, m5_fvg bools), `M1` (m1_trigger, m1_retest), `permissions` (allow_long/allow_short tri-state), `lineage`, `reason_codes`.

**Causality rule:** every feature field SHALL be computed from data observable at `time <= event_time` (forward-PIT). `label_available_time` SHALL be strictly greater than `event_time`. No field inside `features_at_t` MAY derive from a future bar, label, or outcome.

**Versioning:** dataset v2 records schema_version, row count, and a sha256 of the canonical JSONL — recorded for G1.

---

## 3. Feature set contracts (A–F)

Register B–F in `runtime/ai_learning/outcome_classifier.py` as new `INTRADAY_FEATURE_PROFILES` entries. A is an exact replica of baseline `INTRADAY_FEATURE_NAMES` (48 features: `direction`, `sequence_depth`, 10× `ict_m15_*`, 14× `wyckoff_h1/m15_phase=`, 22× `wyckoff_h1/m15_event=`) — unchanged.

| Set | Base | Exact additions |
|---|---|---|
| **A** | `INTRADAY_FEATURE_NAMES` | replica of prior training |
| **B** | A | `context_state` (one-hot D1/H4/H1 status: OK/INCOMPLETE/BLOCKED), `direction_hint` (BULLISH/BEARISH/MIXED/UNKNOWN), `regime_stack` (`TREND_BULL/TREND_BEAR/RANGE/EXPANSION/RETRACEMENT/COMPRESSION/UNKNOWN` per layer) |
| **C** | B | BOS HTF layer bools (D1/H4/H1 bullish/bearish), zones (POI/BSL/SSL count + proximity), lifecycle stage (SETUP/ELIGIBLE/BLOCKED/SUPERSEDED/OUT_OF_CONTEXT) |
| **D** | C | M5 micro (m5_bos, m5_displacement, m5_fvg bools) |
| **E** | D | M1 micro (m1_trigger, m1_retest_state) |
| **F** | E | `allow_long`/`allow_short` tri-state, lineage depth/count, reason_codes one-hot (REASONS incl. MISSING_SNAPSHOT…MISSING_LINEAGE) |

All numeric categorical features are one-hot; cardinal features (`direction`, `sequence_depth`, zone counts/proximity, lineage depth/count) are numeric. Each set is compared against its predecessor (B vs A, C vs B, …).

### F tri-state encoding (MANDATORY — NULL is a THIRD DISTINCT STATE)

`allow_long`/`allow_short` carry THREE semantic states: `ALLOW` (True), `BLOCK` (False), `NO_OPINION` (NULL/None). The spec FORBIDS any `bool(None)`→False collapse. Encode each tri-state feature as **exactly three one-hot columns** (proposal option c):

- `allow_long_allow` = 1 iff ALLOW
- `allow_long_block` = 1 iff BLOCK
- `allow_long_no_opinion` = 1 iff NULL

Same for `allow_short`. This mapping SHALL hold at every hop: snapshot → funnel → dataset → trainer. The trainer MUST reject any row where the three columns do not sum to 1 (i.e., the tri-state was collapsed).

**Known NULL-collapse traps to AVOID (must not appear in the v2 pipeline):**
- `outcome_classifier.py:139` `1.0 if bool(ict.get(name, False)) else 0.0` (collapses three-state to two).
- `engine/plan.py:68` `bos_real.fillna(False).astype(bool)`.
- `wyckoff_intraday_diagnostic_train.py:112-117` `bool(row.get(..., False))`.

---

## 4. Target contract — `label_end_12` (frozen, research-only)

`label_end_12` SHALL be computed EXACTLY as baseline (`wyckoff_intraday_diagnostic_train.py` `_label`):
- Horizon: 12 M15 bars (= 3h) after `event_time`.
- `prior` = previous 20 M15 bars; `scale` = median(`high − low`) of prior (min `1e-9`).
- `signed_move = direction × (close[event+12] − close[event])`.
- `>= +1 range` → `continuation`; `<= −1 range` → `reversal`; else **`failure`**.
- **Ties → `failure`** (unchanged).
- NO SL/TP invention; no costs. Research-level independent target only. **Frozen** — not a tuning lever.

---

## 5. Splits contract (chronological prefix)

| Split | Dates | Usage |
|---|---|---|
| TRAIN | 2006-01-01 → 2008-06-30 | fit ONLY |
| VALIDATION | 2008-07-01 → 2009-06-30 | hyperparameter selection |
| TEST_OOS | 2009-07-01 → 2010-12-31 | FINAL evaluation only |

Strict rule: **no future window enters training**. Split on `event_time`. No random split as primary validation. TEST_OOS MUST NEVER be used for fitting or selection.

---

## 6. Gate acceptance criteria G0–G13

For every gate: evidence artifact proving it + fail action (root cause → fix → re-test → record; **never silent continue**).

| Gate | Check | Evidence artifact | Fail action |
|---|---|---|---|
| G0 | Provenance: lineage documented, auditable | provenance block in artifact w/ snapshot/funnel hashes | fix → re-run → record |
| G1 | Snapshot: dataset hash, schema_version, row count | v2 snapshot manifest + sha256 | fix → re-hash → record |
| G2 | Context State NOT hardcoded; per-event extraction | spot-check N events ≠ UNKNOWN | fix → re-extract → record |
| G3 | Lifecycle per event | lifecycle column distribution report | fix → re-run → record |
| G4 | M5 causal at decision_time only | FULL vs PREFIX diff == 0 | fix → re-extract → record |
| G5 | M1 causal at decision_time only | FULL vs PREFIX diff == 0 | fix → re-extract → record |
| G6 | **NULL third state survives** (mandatory automated test: snapshot→funnel→dataset→trainer, NULL stays NO_OPINION, never False) | test `test_v2_tristate_null_survives_chain` | fix encoding → re-test → record |
| G7 | Funnel reproduction: funnel rows == adapter output | row-count + per-reason counts diff == 0 | fix → re-run → record |
| G8 | FULL vs PREFIX: causal window (no future data) | FULL-vs-PREFIX feature matrix identical test | fix → re-extract → record |
| G9 | Anti-leakage: forbidden-column whitelist scan | automated scan report (0 forbidden hits) | fix → re-scan → record |
| G10 | Splits chronological, no random | split date boundaries + monotonic event_time check | fix → rebuild → record |
| G11 | Reproducible (same seed/data/result) | stored train hash matches re-run | fix → re-test → record |
| G12 | OOS eval only on TEST_OOS | metric report scoped to TEST_OOS | re-evaluate → record |
| G13 | Ablation vs predecessor; no circular optimization | ablation table A→F | re-run → record |

**G8 causal-horizon test:** train/evaluate the classifier twice on identical data — once with features extracted at `time <= event_time` (PREFIX window) and once with the FULL end-of-snapshot window (which may reach future bars). The two feature matrices MUST be byte-identical.

**G9 forbidden-field whitelist scan:** the adapter SHALL reject any candidate feature whose name matches `invalidated_bar|exit_price|MFE|MAE|hit_tp|hit_sl|pnl|profit|return|bars_held|result|label_*|outcome_*` or any retrospective field. The scan runs at dataset materialization and MUST emit a nonzero exit on any hit.

---

## 7. Equality of experiment

Across A–F: SAME corpus, dates, target (`label_end_12`), metrics, seed, split, evaluation procedure. NO hyperparameter optimization on TEST_OOS. Hyperparameters identical to baseline (`deterministic_multinomial_softmax`, lr=0.05, l2=0.0001, seed=20260831, 500 iters) unless changed only on VALIDATION with the change recorded.

---

## 8. Comparison vs baseline — fixed table + classification

Report per set (A–F) vs baseline, fixed fields:

| Field |
|---|
| Population (corpus) |
| N (rows) |
| Features (count + exact list) |
| Causality (G8 status) |
| Leakage (G9 status) |
| OOS stability (per-year spread) |
| Calibration (ECE + calibration curve) |
| Performance (acc, log_loss, Brier, per-class P/R/F1, ROC-AUC, PR-AUC, 3×3 confusion) |
| Coverage (abstention/available cells) |
| Complexity (feature count, params) |
| Reproducibility (G11 status) |

Final classification into EXACTLY ONE of:
`CERTIFIED_IMPROVEMENT` / `NO_MEASURABLE_IMPROVEMENT` / `INSUFFICIENT_EVIDENCE` / `FAILED_CAUSALITY` / `FAILED_PROVENANCE` / `FAILED_REPRODUCIBILITY`.

Decision rule: H1 requires log_loss reduction ≥0.02 AND/OR accuracy gain ≥1pp on TEST_OOS, confirmed by calibration and per-segment analysis. Per-segment cells report only if N ≥ 30.

---

## 9. Non-goals & restrictions

- `can_trade=false` entire mission.
- NO MT5 live or operand data.
- NO `engine/` modification (read-only consumption).
- NO circular optimization (no tuning on TEST_OOS).
- NO git push.
- NO `TRAINING_ELIGIBLE` declaration (provenance BLOCKED; this is DIAGNOSTIC_ONLY).
- NO "edge" language — result is diagnostic, never a signal/order.
- Baseline artifacts byte-for-byte untouched.
- NO backtest/replay as feature source.

---

## Files (write set, from proposal)

New: `ai_outcome_v2_adapter.py`, `ai_outcome_v2_dataset.py`, `ai_outcome_v2_ablation.py`, `ai_outcome_v2_eval.py` (under `scripts/lab/experiments/`). Modified: `outcome_classifier.py` (registry B–F, tri-state), `training_pipeline.py` (extended feature registry), SDD (§5, this doc), contract addendum, worklog.
