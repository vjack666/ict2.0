# Full Six-Timeframe Lineage Gate — 2026-09-21

## Scope

This change closes the previously pending FULL_SIX_TF_MARKETOBJECT_LINEAGE integration boundary.

Required hierarchy: D1 → H4 → H1 → M15 → M5 → M1.

The hierarchy is now mandatory in the operational path. It is not sufficient for the six feeds to exist independently.

## Installed boundaries

- engine.lineage.validate_hierarchical_lineage: global object-graph validation.
- engine.lineage.build_six_tf_lineage_spine: closed-bar six-TF context spine.
- engine.lineage.validate_six_tf_lineage: exact direct-parent hierarchy gate.
- engine.lineage.validate_six_tf_persistence_consistency: exact persisted-MarketState vs closed-feed parity gate.
- engine.setup_builder.build_setups_at: fail-closed when global or six-TF lineage fails.
- engine.daily_motor.build_daily_motor_snapshot: publishes lineage report and returns LINEAGE_INVALID on failure.
- engine.mt5_operational_snapshot.build_object_market_state: persists six-TF context anchors in MarketState.
- engine.mt5_operational_snapshot.build_mt5_operational_snapshot: operational status becomes BLOCKED when lineage is invalid or the persisted six-TF spine drifts from the closed feeds.
- scripts/daily/morning_read.py: refreshes D1/H4/H1/M15/M5/M1 by default.

M5/M1 context anchors are observational ObjectType.CONTRACT objects. They do not replace or mutate FVG/OB/BOS/displacement lifecycle and are explicitly excluded from lifecycle advancement.

## Causal rules

- Same-TF bar indexes may be compared.
- Cross-TF bar indexes are never compared as if they belonged to one clock.
- Cross-TF temporal validation uses timestamps.
- A parent may not be later than its child.
- No object may be later than decision_time.
- Orphan parent/related references fail closed.
- Parent cycles fail closed.
- All six TFs are mandatory.
- Each of the five direct hierarchy edges is mandatory.
- Mixed-symbol six-TF spines fail closed.
- Closed-bar condition is open_time + TF_duration <= decision_time.
- The persisted six-TF MarketState spine must exactly match the spine re-derived from the same closed feeds at decision_time (id, TF, parent, bar index, timestamp, close-price anchor, symbol and source times).

## Real-data control provenance

Existing certified Phase-1 evidence in reports/audits/experiments/temporal/CHATGPT_SIXTF_CAUSAL_SEQUENCE_PHASE1_REAL_B.json records the original source package:

- EURUSD.zip SHA256: 359ef7e3219142422acec473ae786bd07de13043e2cf0e9a532a9e3eb1eab642
- D1: 518f5023ebe365f5dda5d4d1b6c72b375843ec810f578154e58473c9210bb54a
- H4: eb0608477c6da54773ef89a6edabc2217873694e76d17418ab8cc4dc617c7b73
- H1: 7a4669efb9405ccffea5330f343c5bac017d32621ac8590bb0fb47bdd1530f66
- M15: 3a3c23828b4385a93f4c5ce550336b50360c9585f245f00fa364693ecf37598a
- M5 recent profile: 84a4acddfdc3574e8af65c9e6c6242939cc6491dc2577331215dc6944083a3ea
- M1: dace9a21bf98193198d50beed35a7bba683b81c7918bcdcfa1b66974b2379b9a

Control B is 2026-08-24T20:35:00Z, the last audited point with all six TFs available.

Closed-bar geometry:

| TF | selected open | effective close |
|---|---|---|
| D1 | 2026-08-21 00:00Z | 2026-08-22 00:00Z |
| H4 | 2026-08-24 16:00Z | 2026-08-24 20:00Z |
| H1 | 2026-08-24 19:00Z | 2026-08-24 20:00Z |
| M15 | 2026-08-24 20:15Z | 2026-08-24 20:30Z |
| M5 | 2026-08-24 20:30Z | 2026-08-24 20:35Z |
| M1 | 2026-08-24 20:34Z | 2026-08-24 20:35Z |

Audited close-price anchors used by the regression fixture:

| TF | close |
|---|---:|
| D1 | 1.16750 |
| H4 | 1.16648 |
| H1 | 1.16648 |
| M15 | 1.16585 |
| M5 | 1.16593 |
| M1 | 1.16593 |

The September 17 control is intentionally not used for six-TF certification because M1 ends on August 24.

## Tests installed

- Direct D1→H4→H1→M15→M5→M1 path.
- Every one of the five parent edges broken independently => FAIL.
- Each of the six timeframes removed independently => FAIL.
- Future object => FAIL.
- Orphan parent => FAIL.
- Orphan related reference => FAIL.
- Parent cycle => FAIL.
- Cross-TF timestamp ordering with incompatible bar indexes.
- Mixed symbol => FAIL.
- JSON SAVE→LOAD round-trip.
- MarketState SAVE→LOAD round-trip.
- FULL vs PREFIX lineage identity.
- MT5 operational snapshot six-TF gate.
- MT5 operational future invariance.
- Missing M1 => operational BLOCKED.
- Daily motor missing M1 => LINEAGE_INVALID.
- Setup Builder requires complete six-TF lineage.
- Real Control-B OHLC anchors for all six TFs are preserved by the lineage objects.
- Persisted six-TF spine == feed-derived six-TF spine => PASS.
- Tampered persisted M5 anchor => FAIL.
- Missing persisted six-TF spine => FAIL.

A reproducible raw-data verifier is installed at scripts/audit/verify_full_sixtf_lineage_gate.py. It validates the original EURUSD.zip hashes before accepting a result.

## Independent execution performed in this integration session

- six TF present: PASS
- exact direct path: PASS
- closed-only timestamps: PASS
- FULL vs PREFIX: PASS
- five mandatory edges: 5/5 PASS
- six mandatory TF removal checks: 6/6 PASS
- future node rejection: PASS
- real Control-B close anchors preserved: 6/6 PASS
- persisted-vs-derived six-TF parity: PASS
- tampered persisted anchor rejection: PASS
- missing persisted spine rejection: PASS
- earlier global-gate tests for orphan/cycle/cross-TF/future controls: PASS

## External runner limitation

GitHub reports no workflow/check runs for the branch commit. The repository connection can read/write source but does not expose a runnable Actions dispatch in this environment, and the local execution environment cannot resolve github.com/codeload to clone the repository.

Therefore this report does not claim that GitHub Actions ran. The code and test suite are installed; the raw EURUSD.zip verifier and focal pytest command must still be executed in the local repository (or by enabled CI) before the PR is merged as a final regression certification.

Until that final command returns green: can_trade = false
