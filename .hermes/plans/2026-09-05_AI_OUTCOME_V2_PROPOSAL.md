# Proposal: AI Outcome Classifier v2 — Engine-Connected Retraining

**Date:** 2026-09-05
**Status:** PROPOSED (pending spec/design phases)
**Change:** ai-outcome-v2

## Intent

The current IA outcome classifier (`ai_outcome_funnel_bridge.py` + `ai_outcome_dataset.py`) consumes signals/trades from `backtest/replay.py`, NOT the canonical funnel from `engine/episodes.py`. Its Context State is hardcoded to "UNKNOWN". The engine now exposes rich variables (Context State, BOS HTF, zones/lifecycle, M5/M1 tri-state permissions, lineage, reason codes) that the classifier cannot see. This proposal retrains the classifier on the canonical engine funnel with those new variables, without replacing the baseline.

**can_trade=false for the entire mission. No push. No MT5.**

## Baseline (INTACT — comparison reference)

| Field | Value |
|-------|-------|
| Artifact | `reports/audits/experiments/ai/wyckoff_intraday_2006_2010_train.json` + `.jsonl` |
| Corpus | 53,761 rows, 2006-01-02 → 2010-12-31 |
| Target | `label_end_12` (12 M15 bars = 3h) |
| Features | `INTRADAY_FEATURE_NAMES`: direction, sequence_depth, ict_m15_bos/choch/displacement/fvg/sweep (10), wyckoff_h1/m15_phase (14), wyckoff_h1/m15_event (22) |
| Algorithm | `deterministic_multinomial_softmax`, lr=0.05, l2=0.0001, seed=20260831, 500 iters |
| Split | 60/20/20 chronological (TRAIN/VALIDATION/TEST_OOS) |
| OOS metrics | accuracy=0.403, log_loss=1.090 |
| Status | `DIAGNOSTIC_ONLY`, `certified_snapshot=false` |
| **Untouched** | All baseline artifacts preserved byte-for-byte; sha `7a6109…` |

## New Version — What We Build

### Target (preregistered, frozen before training)

- **Horizon**: `label_end_12` (same as baseline: 12 M15 bars / 3h after decision_time).
- **Success**: signed close move vs prior 20-bar median range: >=+1 range -> continuation, <=-1 range -> reversal, else -> failure. Same label rule as baseline.
- **Entry theory**: causal features observable at `time <= event_time` only. No future fields.
- **Ties**: current rule (failure class) — unchanged.
- **Costs**: not incorporated (no SL/TP levels in this research slice).

### Feature Sets (incremental ablation A→F)

| Set | Base | Additions |
|-----|------|-----------|
| **A** (baseline replica) | INTRADAY_FEATURE_NAMES (48 features) | Faithful replica of prior training |
| **B** | A | + context_state (D1/H4/H1 layer status: OK/INCOMPLETE/BLOCKED), direction_hint (BULLISH/BEARISH/MIXED/UNKNOWN), regime_stack (TREND_BULL/TREND_BEAR/RANGE/EXPANSION/RETRACEMENT/COMPRESSION/UNKNOWN) |
| **C** | B | + BOS HTF layers (D1/H4/H1 BOS bullish/bearish bool), canonical zones (POI/BSL/SSL count + proximity), lifecycle stage (SETUP/ELIGIBLE/BLOCKED/SUPERSEDED/OUT_OF_CONTEXT) |
| **D** | C | + M5 micro-structure (M5 BOS, M5 displacement, M5 FVG bools) |
| **E** | D | + M1 micro-confirmation (M1 trigger bool, M1 retest state) |
| **F** | E | + permissions tri-state (allow_long/allow_short as 3 values: ALLOW/BLOCK/NO_OPINION), lineage depth/count, reason codes (MISSING_SNAPSHOT...MISSING_LINEAGE, one-hot) |

Each set is compared against its predecessor (B vs A, C vs B, ...). All sets include anti-leakage guards.

### Pipeline

```
engine/episodes.py (canonical funnel)
  -> new adapter: engine->features_at_t (per-event causal extraction)
    -> ai_outcome_dataset_v2.py (materializer, same contract structure)
      -> training_pipeline.py (same trainer, extended feature registry)
        -> evaluation (OOS, ablation, calibration)
```

### Period and Splits

| Split | Dates | Rows (est.) | Purpose |
|-------|-------|-------------|---------|
| TRAIN | 2006-01-01 -> 2008-06-30 | ~60% | Fit only |
| VALIDATION | 2008-07-01 -> 2009-06-30 | ~20% | Hyperparameter selection |
| TEST_OOS | 2009-07-01 -> 2010-12-31 | ~20% | Final evaluation (never for fitting or selection) |

Chronological prefix split. No random splits as primary validation.

### Metrics (beyond accuracy)

- log_loss, Brier score, precision/recall/F1 per class
- ROC-AUC and PR-AUC (one-vs-rest, if applicable)
- Confusion matrix (full 3x3)
- Calibration curve + ECE (Expected Calibration Error)
- Per-year, per-context-state, per-permission, per-zone-type, per-setup-eligibility, per-regime performance
- Sample size per cell (minimum 30 for reporting)

## Files — Write Set (proposed, NOT executed)

### New files
| File | Purpose |
|------|---------|
| `scripts/lab/experiments/ai_outcome_v2_adapter.py` | Engine->features_at_t causal adapter |
| `scripts/lab/experiments/ai_outcome_v2_dataset.py` | Materializer v2 (engine funnel -> dataset) |
| `scripts/lab/experiments/ai_outcome_v2_ablation.py` | Feature set A->F ablation runner |
| `scripts/lab/experiments/ai_outcome_v2_eval.py` | OOS evaluation + comparison vs baseline |

### Modified files
| File | Change |
|------|--------|
| `runtime/ai_learning/outcome_classifier.py` | Register extended feature sets B-F; tri-state encoding |
| `runtime/ai_learning/training_pipeline.py` | Support extended features; same trainer |
| `docs/planificacion/SDD_AI_OUTCOME_CLASSIFIER_V1.md` | Add v2 section (section 5) referencing this proposal |
| `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md` | Addendum: v2 target, feature sets, gates |
| `.hermes-worklog/` | Mission log entry |

### NOT modified
- Baseline artifacts (`wyckoff_intraday_2006_2010_train.json`, `.jsonl`)
- `backtest/replay.py`, `engine/` (read-only consumption)
- Any file that would break existing v1 pipeline

## Hypothesis

- **H1**: The new engine variables (Context State, BOS HTF, zones/lifecycle, M5, M1, tri-state permissions, lineage, reason codes) provide **real, reproducible, causal OOS predictive information** beyond the baseline feature set. Measured by: log_loss reduction >=0.02 and/or accuracy improvement >=1pp on TEST_OOS, confirmed by calibration and per-segment analysis.
- **H0**: The new variables add no measurable OOS improvement or only increase complexity without signal. If H0 holds, feature set A is retained.

Both hypotheses are falsable. The result is classified as:
- `CERTIFIED_IMPROVEMENT` — H1 confirmed, metrics improve materially on OOS
- `NO_MEASURABLE_IMPROVEMENT` — H0 cannot be rejected
- `INSUFFICIENT_EVIDENCE` — sample size or provenance prevents conclusion
- `FAILED_CAUSALITY` — leakage or temporal violations detected
- `FAILED_PROVENANCE` — provenance chain broken
- `FAILED_REPRODUCIBILITY` — results not reproducible

## Gates G0–G13

| Gate | Check |
|------|-------|
| G0 | Provenance: data source lineage documented and auditable |
| G1 | Snapshot: dataset hash, schema version, row count recorded |
| G2 | Context State: not hardcoded; extracted from engine per event |
| G3 | Lifecycle: setup eligibility state captured per event |
| G4 | M5 causal: micro-structure features extracted at decision_time only |
| G5 | M1 causal: trigger features extracted at decision_time only |
| G6 | NULL third state: tri-state allow_long/allow_short preserved as 3 values (not bool(Null->False)) |
| G7 | Funnel reproduction: engine funnel rows match adapter output |
| G8 | FULL vs PREFIX: causal window respected (no future data in features) |
| G9 | Anti-leakage: no invalidated_bar, exit, MFE/MAE, hit_tp/hit_sl, or retrospective labels as features |
| G10 | Splits: chronological, no random; TRAIN/VALIDATION/TEST_OOS |
| G11 | Training reproducible: same seed, same data, same result |
| G12 | OOS evaluation: metrics reported on TEST_OOS only for final comparison |
| G13 | Ablation: each feature set compared against predecessor; no circular optimization |

## Anti-Leakage Audit Checklist

Forbidden as features: `invalidated_bar`, `exit_price`, `MFE`, `MAE`, `hit_tp`, `hit_sl`, `pnl`, `profit`, `return`, `bars_held`, `result`, `label_*`, `outcome_*`, any retrospective field. Verified by: explicit column whitelist per feature set + automated scan in adapter.

## Restrictions

- `can_trade=false` — entire mission
- IA does not modify `engine/` — read-only consumption
- No circular optimization (no tuning on TEST_OOS)
- No MT5 live data
- No git push
- No random split as primary validation
- No declaration of `TRAINING_ELIGIBLE` or `edge`

## Recommended Document Actions

| Action | Document | Justification |
|--------|----------|---------------|
| **UPDATE** | `docs/planificacion/SDD_AI_OUTCOME_CLASSIFIER_V1.md` | Add section 5 for v2 (same document, v1 preserved) |
| **UPDATE** | `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md` | Addendum with v2 target, feature sets, gates |
| **THIS FILE** | `.hermes/plans/2026-09-05_AI_OUTCOME_V2_PROPOSAL.md` | Change-level proposal (this document) |
| NO CREATE | New SDD | v2 integrates into existing SDD, no incompatible purpose |

## Proposal Question Round

Blocked from interactive mode — listing assumptions needing review:

1. **Target stability**: Is `label_end_12` confirmed as the v2 target, or should v2 explore label_end_6/8/12 as a secondary ablation? (Assumed: fixed at 12 to match baseline for fair comparison.)
2. **Sample size**: With 2006–2010 (~54K rows) and 6 feature sets, is the per-cell sample size sufficient for per-segment analysis? (Risk: some segments may have <30 rows; will report and flag.)
3. **Engine replay feasibility**: The canonical engine funnel may produce fewer rows than the backtest funnel (stricter gates). Is row-count reduction acceptable? (Assumed: yes, quality over quantity.)
4. **Tri-state encoding**: How should NULL (no opinion) be encoded? Options: (a) separate category per feature, (b) numeric -1/0/1 with NULL as 0, (c) three one-hot columns. (Assumed: three one-hot columns for maximum expressiveness.)

## Rollback Plan

- All new files are additive; no existing file is overwritten without backup
- `git stash` or branch revert if issues arise
- Baseline artifacts never touched; v1 pipeline unaffected

## Success Criteria

- [ ] Feature sets A-F trained and evaluated on same corpus/split
- [ ] OOS metrics reported for each set with confidence intervals
- [ ] Ablation comparison: each set vs predecessor
- [ ] Baseline comparison: set A vs original training metrics
- [ ] Anti-leakage audit passes G9
- [ ] All gates G0-G13 documented and checked
- [ ] Result classified per outcome categories above
