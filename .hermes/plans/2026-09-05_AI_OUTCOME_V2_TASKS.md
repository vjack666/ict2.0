# Tasks: AI Outcome Classifier v2 — Engine-Connected Retraining

**Change:** ai-outcome-v2 | **Date:** 2026-09-05 | **Status:** TASKS (→ apply)
**Design (authoritative):** `.hermes/plans/2026-09-05_AI_OUTCOME_V2_DESIGN.md` (R3 resolutions included)
**Constraints:** `can_trade=false`, no MT5, `engine/` read-only, no TEST_OOS tuning, no `TRAINING_ELIGIBLE`, DIAGNOSTIC_ONLY, baseline v1 byte-unchanged, NO git push (local commits only).

> **STRICT TDD MODE IS ACTIVE.** Test runner: `python -m pytest` (system python 3.14.6; `.venv` is BROKEN — never use it). Every implementation task below writes its failing test(s) FIRST (RED), then implements (GREEN), then re-runs the listed verification command.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2,300–2,400 (T1 70, T2 340, T3 560, T4 440, T5 135, T6 70, T7 180, T8 320, T9 250) |
| 400-line budget risk | **High** |
| Chained PRs recommended | **No — repository forbids `git push`**; substitute = sequential LOCAL commit units (CU-1…CU-5), each reviewable via `git diff <unit>` before the next starts |
| Suggested split | Local commits CU-1 → CU-2 → CU-3 → CU-4 → CU-5 (see table) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending (no PR chain possible; local commit units) |

```text
Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: High
```

**Decision needed before apply: YES** — total far exceeds the 400-line review budget; orchestrator must confirm local commit-unit plan (CU-1…CU-5) and that T3/T8 (largest single new modules) are acceptable as reviewable new-file units. No remote PRs exist (push prohibited); `git push` remains forbidden for the whole change.

| Unit | Tasks | Goal | Commit note |
|------|-------|------|-------------|
| CU-1 | T1 | Schema-versioned `load_causal_jsonl` relaxation (v1 byte-unchanged) | ~70 lines; foundation |
| CU-2 | T2 | `V2_FEATURE_PROFILES` + `_v2_features` + tri-state encoder + dispatch | ~340 lines; no data flow yet |
| CU-3 | T3 | Engine→v2 causal adapter + frames pinning (sha256, FULL-vs-PREFIX) | ~560 lines; new standalone module |
| CU-4 | T4 | v2 materializer (JSONL + audit + hashes + scans + tri-state guard) | ~440 lines |
| CU-5 | T5 | Diagnostic wiring (profile check + end-to-end A/F artifacts) | ~135 lines |
| CU-6 | T6 | MANDATORY G6 chain test (NULL survives snapshot→funnel→dataset→trainer) | ~70 lines; depends CU-2–CU-5 |
| CU-7 | T7 | Ablation runner A→F (equality of experiment) | ~180 lines |
| CU-8 | T8 | Eval runner (OOS, per-segment N≥30, baseline, 6-category) | ~320 lines |
| CU-9 | T9 | Gate evidence G0–G13 + docs addenda + worklog + index + final commit | ~250 lines; local only |

---

## Dependency Map & First Safe Batch

- **FIRST SAFE BATCH (parallel, disjoint write sets):** T1 (`diagnostic_training.py` + `tests/test_ai_outcome_v2_schema.py`) and T2 (`outcome_classifier.py` + `tests/test_ai_learning_outcome_classifier.py` + `tests/test_ai_outcome_v2_tristate.py` partial). No shared files → can run concurrently.
- **Chain after batch:** T3 → T4 → T5 → T6 → T7 → T8 → T9.
- **Parallelizable later:** T4 and T5 may start as soon as T3/T2+T1 respectively complete (T5 needs T1+T2 only for its code change, but its end-to-end reproducibility test needs real T4-materialized rows → keep sequential per design §10).

```
T1 ─┐
    ├─► T5 ─► T6 ─► T7 ─► T8 ─► T9
T2 ─┴─► T3 ─► T4 ─┘
(parallel: T1 ∥ T2 first)
```

---

## Task List

| # | Task | Objective | Files (create/modify) | Acceptance criteria (test names) | Deps | Cx | Δlines | Verification |
|----|------|-----------|----------------------|----------------------------------|------|----|--------|---------------|
| **T1** | Schema-versioned `load_causal_jsonl` relaxation | Make `load_causal_jsonl` accept `schema_group="engine_v2"` rows while v1 rows stay byte-unchanged | Modify `runtime/ai_learning/diagnostic_training.py` (lines ~192–203, exact patch design §4.1); Create `tests/test_ai_outcome_v2_schema.py` | `test_v2_rows_pass_load_causal_jsonl` (v2 row loads, v1 row still loads, missing-keys row raises) | — | S | 70 | `python -m pytest tests/test_ai_outcome_v2_schema.py -q` |
| **T2** | V2 registry + `_v2_features` + tri-state encoder + dispatch | Add `V2_*` constants, `V2_FEATURE_PROFILES`, `_v2_features` (§5.4 flat-column rules), extend `_features`/`from_dict`/`train` membership (v1 tuples byte-identical) | Modify `runtime/ai_learning/outcome_classifier.py`; Create/extend `tests/test_ai_outcome_v2_tristate.py` + `tests/test_ai_learning_outcome_classifier.py` | `test_v2_registry_no_collision`, `test_v2_artifact_validates_profile`, `test_v2_tristate_collapse_rejected` (`sum!=1`→`TRI_STATE_COLLAPSED`), `test_v2_no_none_false_collapse` | — | M | 340 | `python -m pytest tests/test_ai_learning_outcome_classifier.py tests/test_ai_outcome_v2_tristate.py -q` |
| **T3** | Engine→v2 causal adapter | Build `adapt_funnel_artifact`: per-event causal extraction (context_state, BOS HTF, zones, lifecycle, M5, M1, permissions, lineage, reason codes), verbatim tri-state serializer, pinned frames sha256 + PREFIX window, rejected candidates preserved in audit | Create `scripts/lab/experiments/ai_outcome_v2_adapter.py`; Create `tests/test_ai_outcome_v2_adapter.py` + `tests/test_ai_outcome_v2_causality.py`; extend tristate tests | `test_v2_funnel_reproduction` (G7, row+reason counts), `test_v2_full_vs_prefix_identical` (G8, feature matrices byte-identical), `test_v2_A_parity_with_baseline_intraday` (G6, `atol=1e-9`) | T2 | L | 560 | `python -m pytest tests/test_ai_outcome_v2_adapter.py tests/test_ai_outcome_v2_causality.py tests/test_ai_outcome_v2_tristate.py -q` |
| **T4** | v2 dataset materializer | Write canonical JSONL + audit JSONL (rejected candidates with `reason_codes`, `label_end_12=null`), manifest (raw_sha256/schema_hash/row_count/reason_counts/funnel_checksum/frames_sha256), forbidden-field scan + future-feature scan + tri-state guard, strict-increasing event_time, nonzero exit on any hit | Create `scripts/lab/experiments/ai_outcome_v2_dataset.py`; extend `tests/test_ai_outcome_v2_causality.py` + `tests/test_ai_outcome_v2_schema.py` | `test_v2_forbidden_field_scan` (G9), `test_v2_future_feature_rejected` (G8/G9), `test_v2_event_time_and_identity` (G1/G10), `test_v2_hashes_and_manifest` (G1) | T3 | M | 440 | `python -m pytest tests/test_ai_outcome_v2_causality.py tests/test_ai_outcome_v2_schema.py -q` |
| **T5** | Diagnostic wiring (DIAGNOSTIC_ONLY) | Extend `run_diagnostic_training` profile check to accept `_V2_FEATURE_TUPLES`; end-to-end v2 artifacts for A and F through the existing diagnostic path; chronological split + reproducibility verified | Modify `runtime/ai_learning/diagnostic_training.py` (line ~420 additive); extend `tests/test_ai_outcome_v2_schema.py`; Create `tests/test_ai_outcome_v2_repro.py` | `test_v2_temporal_splits` (G10, TRAIN 2006-01→2008-06 / VAL 2008-07→2009-06 / OOS 2009-07→2010-12), `test_v2_reproducible` (G11, same seed/data → identical artifacts) | T1,T2,T4 | M | 135 | `python -m pytest tests/test_ai_outcome_v2_schema.py tests/test_ai_outcome_v2_repro.py -q` |
| **T6** | MANDATORY G6 chain test | Prove a NULL permission survives snapshot→funnel→dataset→trainer as `no_opinion=1, allow=0, block=0`, never `bool(None)→False` | Extend `tests/test_ai_outcome_v2_tristate.py` | `test_v2_tristate_null_survives_chain` (G6, authoritative anti-collapse guard) | T2,T3,T4,T5 | S | 70 | `python -m pytest tests/test_ai_outcome_v2_tristate.py::test_v2_tristate_null_survives_chain -q` |
| **T7** | Ablation runner A→F | Run sets A→F under equality of experiment (same corpus/dates/target `label_end_12`/seed 20260831/lr 0.05/l2 1e-4/500 iters/60-20-20 split); emit A→F table with predecessor deltas (G13); no TEST_OOS tuning | Create `scripts/lab/experiments/ai_outcome_v2_ablation.py` | G13 evidence: ablation table A→F with B-vs-A … F-vs-E deltas; fixed hyperparameters; no circular optimization | T4,T5 | M | 180 | `python scripts/lab/experiments/ai_outcome_v2_ablation.py --smoke` then `python -m pytest tests/ -q` |
| **T8** | Eval runner | OOS-only metrics (acc, log_loss, Brier, per-class P/R/F1, ROC-AUC, PR-AUC, 3×3 confusion), calibration (curve+ECE), per-segment tables with N≥30 guard (`insufficient_n` flag), baseline comparison fixed table, final 6-category classification | Create `scripts/lab/experiments/ai_outcome_v2_eval.py` | G12: final table scoped to TEST_OOS only (no VAL/TRAIN); classification into exactly one of the 6 outcome categories per H1 decision rule (log_loss ↓≥0.02 AND/OR acc ↑≥1pp) | T7 | L | 320 | `python scripts/lab/experiments/ai_outcome_v2_eval.py --artifacts <dir> --test-rows <jsonl>` on TEST_OOS + `python -m pytest tests/ -q` |
| **T9** | Gate evidence + docs + worklog + commit units | Assemble G0–G13 evidence artifacts (manifests, scans, gate checklist) in `reports/audits/experiments/ai/`; add v2 section 5 to SDD doc + contract addendum; mission worklog + `.hermes-index.md`; local selective commit units CU-1…CU-9 (NO push) | Modify `docs/planificacion/SDD_AI_OUTCOME_CLASSIFIER_V1.md`, `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md`, `.hermes-index.md`; Create `.hermes-worklog/2026-09-05_AI_OUTCOME_V2_*.md` + gate evidence under `reports/audits/experiments/ai/`; git commits (local) | Gates G0–G13 each with evidence artifact + fail-action record; full v2 test suite green; baseline artifacts sha `7a6109…` byte-identical; no push performed | T1–T8 | M | 250 | `python -m pytest tests/test_ai_outcome_v2_*.py tests/test_ai_learning_outcome_classifier.py tests/test_ai_learning_training_pipeline.py -q` + gate checklist diff |

---

## Task-Level Risks

- **T2/T6 (tri-state)**: any future edit re-introducing `bool(None)→False` silently breaks G6; `sum==1` is only a well-formedness invariant (does not catch `None→False`) — the chain test T6 is the authoritative guard.
- **T3 (frames pinning)**: `data/raw/EURUSD/EURUSD_M1.parquet` and `EURUSD_M5.parquet` currently show as MODIFIED in `git status` — on-disk bytes differ from HEAD; manifest must bind actual on-disk sha256, deviation must be root-caused before G7/G11 evidence (likely from live-card work, not this change).
- **T3 (provenance)**: adapter re-invokes `MTFNavigator.navigate(decision_time, exec_tf="H1")` per event — must stay forward-PIT (PREFIX only); any future-bar access fails G8.
- **T4 (row reduction)**: stricter engine funnel may yield far fewer accepted rows than baseline 53,761; severity = some OOS per-segment cells drop below N≥30 (flagged, never fabricated).
- **T7 (equality)**: any divergence in corpus/split/seed/hyperparameters across A–F invalidates G13 — fixed config must be a single shared constant.
- **T8 (classification)**: six-category result is diagnostic only; no "edge"/TRAINING_ELIGIBLE language anywhere in eval output.
- **T9**: plan artifacts (proposal/spec/design/tasks) remain uncommitted until CU-9; final commit must be local-only, no push (git push prohibition from governance).

## Non-goals (reminder for apply)

No `openspec/`; no `engine/` modification; no `backtest/` imports for data; no baseline artifact writes; no MT5; `.venv` never used; no implementation in this phase — tasks only.