# ChatGPT — Six-timeframe causal sequence Phase 1 verification

Date: 2026-09-21

## Scope

This phase extends the already-approved H4/M15 causal base toward the normal project hierarchy:

`D1 → H4 → H1 → M15 → M5 → M1`

The purpose of Phase 1 is **not** to certify the final six-timeframe funnel. It establishes:

- closed-only access to all six layers;
- strict cross-timeframe provenance by UTC timestamp;
- a real HTF BOS/CHOCH context object that must pre-exist the LTF event;
- persistent context lineage in `SequenceState`;
- an event-driven core sequence that cannot collapse SWEEP, DISPLACE, BOS and RETURN into one candle.

Base approved SHA:

`c8103747956db13403fe8b42ce858288ba35c442`

Phase-1 branch:

`chatgpt/six-tf-causal-sequence-phase1-20260921`

## Engine changes

### `engine/poi_anchor.py`

Adds strict HTF structure provenance.

A resolved parent is a real D1/H4/H1 BOS or CHOCH with its original timeframe, timestamp, level and bar index. Cross-TF causal ordering uses real timestamps, **not bar indices from different clocks**.

Strict rule:

`parent_time < ltf_event_time`

A parent confirmed on the same close is rejected.

The returned object is `Role.CONTEXT`. It is explicitly **not** fabricated as an institutional OB/FVG POI.

Verified blob:

`dd6cfcc3156f97fcc30cb21578c68f745ed134b2`

### `engine/sequence.py`

Adds persistent `context_id`, six-layer birth snapshots and strict later-bar guards for the core sequence.

Core temporal contract:

`SWEEP → DISPLACE → BOS → RETURN`

Each transition must occur on a later LTF bar than its predecessor.

`LIQUIDITY` and `SWEEP` may describe the same sweep candle because liquidity is the swept reference, not an additional core stage.

Signals expose:

- `sequence_span_bars`;
- `strict_multibar_core`;
- `event_ids.CONTEXT`;
- the real HTF context object in `event_objects`.

Verified blob:

`f804e0c02546fcbd262f3d9def8d999363fb973a`

## Regression tests

A temporary isolated reconstruction was used for execution. The modified engine files in that reconstruction hash exactly to the GitHub blobs above; the relevant unchanged `engine/plan.py` and `engine/multitf_context.py` also match the approved lineage.

Executed test set:

`80 passed, 0 failed`

This includes six new Phase-1 tests plus existing sequence, event-patience, sequential-outcome, MTF navigation, MTF replay, snapshot invariance and intraday MTF/LTF regressions.

The six new regressions demonstrate:

1. cross-TF ordering uses UTC time rather than incompatible bar indices;
2. an HTF parent on the same close is rejected;
3. the birth snapshot freezes D1/H4/H1/M15/M5/M1;
4. a candle with sweep + displacement + BOS flags advances only to SWEEP;
5. a complete synthetic sequence occurs on bars `1 → 2 → 3 → 4`;
6. SAVE/LOAD preserves `context_id` and the HTF context MarketObject.

Python syntax/import compilation for the modified engine and new verifier/tests also passed.

## Authentic EURUSD verification

Original source:

`EURUSD.zip`

ZIP SHA256:

`359ef7e3219142422acec473ae786bd07de13043e2cf0e9a532a9e3eb1eab642`

All six selected source hashes match `benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json`:

- D1 `518f5023ebe365f5dda5d4d1b6c72b375843ec810f578154e58473c9210bb54a`
- H4 `eb0608477c6da54773ef89a6edabc2217873694e76d17418ab8cc4dc617c7b73`
- H1 `7a4669efb9405ccffea5330f343c5bac017d32621ac8590bb0fb47bdd1530f66`
- M15 `3a3c23828b4385a93f4c5ce550336b50360c9585f245f00fa364693ecf37598a`
- M5 `84a4acddfdc3574e8af65c9e6c6242939cc6491dc2577331215dc6944083a3ea`
- M1 `dace9a21bf98193198d50beed35a7bba683b81c7918bcdcfa1b66974b2379b9a`

### Real Control B

Decision time:

`2026-08-24T20:35:00Z`

All six layers are available and closed-only:

- D1 as-of `2026-08-24T00:00:00Z`
- H4 as-of `2026-08-24T20:00:00Z`
- H1 as-of `2026-08-24T20:00:00Z`
- M15 as-of `2026-08-24T20:30:00Z`
- M5 as-of `2026-08-24T20:35:00Z`
- M1 as-of `2026-08-24T20:35:00Z`

Result:

- all six layers available: PASS
- all six layers `<= T`: PASS
- FULL versus PREFIX future invariance at T: PASS
- HTF provenance FULL versus PREFIX: PASS
- strict parent-before-T rule: PASS

Real causal HTF examples resolved at Control B:

- bullish parent: H1 BOS at `2026-08-18T17:00:00Z`, level `1.15799`
- bearish parent: H1 BOS at `2026-08-21T17:00:00Z`, level `1.16962`

Both are strictly earlier than Control B and unchanged when future data is present.

### Control A limitation

Control A is `2026-09-17T18:20:00Z`.

The selected M1 source ends at:

`2026-08-24T20:38:00Z`

Therefore Control A cannot honestly be used as a six-timeframe control with this package. Classification:

`OUT_OF_RANGE_NOT_MISSING_DATA`

No synthetic M1 bars were created to manufacture coverage.

## H4/M15 regression boundary

Before the new evidence/test files were added, GitHub comparison against the approved base showed that the only engine files modified by Phase 1 were:

- `engine/poi_anchor.py`
- `engine/sequence.py`

The approved H4/M15 replay implementation remains unchanged in the branch lineage:

- `engine/market_state.py`
- `engine/historical_event_objects.py`
- `engine/causal_replay.py`
- `scripts/audit/verify_causal_replay_ab.py`

The previous H4/M15 certification is therefore not replaced by this phase. Hermes should still rerun the lightweight local H4/M15 A/B smoke check after installation.

## Verdict

**PASS — SIX_TF_CAUSAL_SEQUENCE_PHASE1_ONLY**

What is now supported:

`six closed-only layers + strict HTF provenance + persistent context lineage + strict multibar sequence core`

What is **not** yet certified:

- full MarketObject lineage across every one of the six TFs;
- the final six-TF funnel;
- episodes;
- training corpus;
- GRU;
- MT5;
- production trading.

The next engineering phase is to turn the six available layers into a complete cross-TF MarketObject lineage:

`D1 context → H4 structure/POI → H1 confirmation → M15 formation → M5 refinement → M1 execution`
