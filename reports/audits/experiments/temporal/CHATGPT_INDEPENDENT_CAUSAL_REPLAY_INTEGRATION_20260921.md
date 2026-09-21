# ChatGPT independent integration verification — causal replay H4/M15

Date: 2026-09-21

## Scope

This verification is limited to the H4/M15 causal replay / MarketState snapshot integration. It does **not** certify the six-timeframe funnel, episodes, GRU, MT5 or trading readiness.

Source GitHub branch: `hermes/evidencia-ict-replay-pass-20260920`
Source branch HEAD verified before publication: `e6298c644b63338ca6574503ccf5b00c802a55da`
Core corrected code commit in that lineage: `79b71eb102202f03a13173a8f4b610a46d0bdc0d`
Temporary ORIGINAL snapshot base used for independent reconstruction: `7cc4e2df7d3a689cd279d5ae5c059e424bdc5864`

## Real data provenance

Input ZIP: `/mnt/data/EURUSD.zip`
ZIP SHA256: `359ef7e3219142422acec473ae786bd07de13043e2cf0e9a532a9e3eb1eab642`
Benchmark manifest used by the verifier: `benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json`
Manifest SHA256 in the temporary reconstruction: `d144158eb7e626ad68c0ca06adf33afa991f6b5a3a645ef0a00a530cccb82bbd`

The verifier validated all six selected source SHA256 values:

- D1 `518f5023ebe365f5dda5d4d1b6c72b375843ec810f578154e58473c9210bb54a`
- H4 `eb0608477c6da54773ef89a6edabc2217873694e76d17418ab8cc4dc617c7b73`
- H1 `7a4669efb9405ccffea5330f343c5bac017d32621ac8590bb0fb47bdd1530f66`
- M15 `3a3c23828b4385a93f4c5ce550336b50360c9585f245f00fa364693ecf37598a`
- M5 `84a4acddfdc3574e8af65c9e6c6242939cc6491dc2577331215dc6944083a3ea`
- M1 `dace9a21bf98193198d50beed35a7bba683b81c7918bcdcfa1b66974b2379b9a`

## Causal/integration tests

Direct tests touching `MarketState`, `historical_event_objects`, causal replay, episodes and setup integration:

`93 passed in 0.63s`

The focused integration subset containing the newly reconstructed replay/audit tests also passed:

`55 passed in 0.21s`

## Authentic A/B verification

Result:

- `all_pass: true`
- Control A: `PASS_H4_M15_PIT_PILOT`, 28 MarketObjects, 8 with parent
- Control B: `PASS_H4_M15_PIT_PILOT`, 26 MarketObjects, 6 with parent
- FULL/PREFIX producer: PASS at all 6 anchors in A and all 6 anchors in B
- FULL/PREFIX projection: PASS at all anchors
- future invalidation metadata leaks: none
- SAVE/LOAD full-metadata roundtrip: PASS
- reversed input order: PASS
- future injection producer: PASS
- future injection replay: PASS
- same-close parent links: none

Result JSON SHA256: `5530947d67a52ee7793f886b5e1a127ea8ea0f13c785bb14c0cac3c01eb0bb15`

## Wider suite

A complete repository pytest attempt was also executed after restoring tracked files that were omitted from the portable snapshot. Result:

`847 passed, 2 skipped, 7 failed`

The seven failures are outside the H4/M15 causal replay integration:

1. one training-gate test requires the missing local `OOS_REDTEAM_VERDICT.json` artifact;
2. one evidence-gate test requires the missing local `data/materialized/v2/ai_outcome_v2_full.jsonl.manifest` artifact;
3. four tests require a parquet engine (`pyarrow` or `fastparquet`), which is unavailable in this isolated Linux runtime;
4. one MT5 launcher assertion is Windows-path-specific and fails under POSIX `pathlib` semantics.

No project code or test expectation was weakened to hide those failures. With only those seven explicitly environment/artifact-blocked tests deselected, the remainder of the repository suite produced:

`847 passed, 2 skipped, 7 deselected in 27.07s`

## Verdict

**APPROVED for the H4/M15 causal replay integration scope only.**

The causal replay / snapshot contract is independently reproduced as PASS against the authentic EURUSD data. This does not authorize claims about the six-TF funnel, episodes, GRU, MT5 or production trading.
