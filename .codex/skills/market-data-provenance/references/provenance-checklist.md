# Provenance checklist and result shape

Read this reference when performing an actual audit or certification. Keep
provider-specific API details in the provider's official documentation; this
file defines the evidence that must survive the transformation.

## Required evidence groups

### Source identity

- `provider`
- `dataset_id`
- `venue`
- `symbol`
- `contract_or_continuous_policy`
- `rollover_rule`
- `license_and_permitted_use`
- `source_documentation_refs`
- `acquired_at_utc`
- `request_parameters`

For CME `6E`, do not report only `EURUSD` or a generic "futures" label. Record
the actual contract identity or the documented continuous-contract construction.

### Schema and time

- `columns` and declared dtypes
- `timestamp_field`
- `timezone_policy`
- `session_policy`
- `bar_boundary_semantics`
- `open_interest_semantics`
- `volume_semantics`
- `lookahead_policy`

### Integrity metrics

Record before/after counts for each stage and the counts of:

- duplicate logical keys;
- non-monotonic timestamps;
- gaps and out-of-session rows;
- invalid OHLC rows;
- null/non-finite values;
- missing or unavailable volume/open interest;
- rollover transitions;
- dropped, repaired, or imputed rows.

### Join lineage

For `6E` ↔ `EURUSD`, record:

- join key and direction (`exact`, `backward_asof`, or another contracted rule);
- tolerance and session/timezone conversion;
- source row identifiers on both sides;
- matched, unmatched, duplicate, and tolerance-violation counts;
- proof that all joined data is available by decision time.

### Reproducibility

- artifact path, byte size, SHA-256 for every input/intermediate/output;
- manifest path and manifest hash;
- generator script and generator commit;
- repository root, branch/ref, and worktree state;
- Python and package versions;
- command line or structured invocation parameters;
- logs and evidence references.

## Result states

Use one top-level status and retain individual check results:

```json
{
  "status": "PASS | REVIEW | BLOCKED | NOT_RUN",
  "mode": "AUDIT_ONLY | INGEST | JOIN | CERTIFY",
  "as_of_utc": "...",
  "source_identity": {},
  "checks": [
    {
      "id": "SOURCE_IDENTITY",
      "status": "PASS | REVIEW | BLOCKED | NOT_RUN",
      "evidence_refs": [],
      "details": ""
    }
  ],
  "artifacts": [
    {
      "path": "...",
      "sha256": "...",
      "bytes": 0,
      "role": "input | intermediate | output"
    }
  ],
  "generator": {
    "script": "...",
    "commit": "...",
    "worktree_state": "CLEAN | DIRTY | UNKNOWN"
  },
  "next_action": ""
}
```

`CERTIFIED` is not a result state in this checklist; it is allowed only when
the top-level checks are `PASS`, all required evidence is present, hashes and
manifest agree, and the generator worktree is `CLEAN`. Keep scientific or
trading conclusions in their own contracts.
