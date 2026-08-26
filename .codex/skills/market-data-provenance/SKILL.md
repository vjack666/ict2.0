---
name: market-data-provenance
description: Audit and certify market-data provenance, temporal joins, and reproducibility for CME and FX datasets; use when ingesting, joining, validating, or certifying research data.
---

# Market Data Provenance

Use this skill for any task that downloads, normalizes, joins, validates, or
certifies market data used by the ICT/Hermes research pipeline. Its purpose is
to make provenance and reproducibility failures visible before an experiment,
backtest, training run, or promotion.

## Authority and scope

- Default to read-only audit. Do not download data, overwrite datasets, alter
  manifests, or run experiments unless the user explicitly authorizes that
  operation and the relevant project contract permits it.
- Work only in the operational checkout identified by the repository context.
  Preserve unrelated dirty changes and never use broad staging or destructive
  cleanup.
- This skill certifies data lineage and mechanical integrity. It does not
  decide Wyckoff theory, label correctness, scientific hypotheses, edge, or
  trading permissions.
- Context7 may verify external APIs and library behavior for the installed
  versions. It is not an authority for CME licensing, market methodology,
  experimental conclusions, or promotion.

For detailed fields and result states, read
[references/provenance-checklist.md](references/provenance-checklist.md).

## Workflow

### 1. Establish the requested mode

Classify the task as `AUDIT_ONLY`, `INGEST`, `JOIN`, or `CERTIFY`. If the mode
is not explicit, use `AUDIT_ONLY`. Before any mutating operation, identify the
authorization, contract, output path, and rollback/recovery plan.

Inspect the repository contracts, current branch, `git status --short`, existing
loaders, manifests, audit reports, and generator scripts. Do not assume that a
historical certificate or a clean-looking report proves current provenance.

### 2. Identify the source and instrument exactly

Record, without inference:

- provider, endpoint, account or dataset identifier, license and permitted use;
- venue, symbol, currency, contract month, continuous-contract policy, and
  rollover rule for CME `6E`;
- schema, price/volume units, OHLCV fields, open-interest field and its
  observation semantics;
- acquisition time in UTC, request parameters, pagination, filters, and source
  documentation URL;
- timezone, trading sessions, holidays, bar boundary, and whether timestamps
  represent open, close, exchange, or publication time.

If any item is unknown, mark it `UNKNOWN` and do not silently fill it from a
proxy. Missing open interest is `UNAVAILABLE`, never zero by assumption.

### 3. Validate the raw and normalized data

Check and report, separately for each source and transformation:

- required columns and dtypes;
- timezone awareness and normalization policy;
- monotonic timestamps, duplicate logical keys, gaps, out-of-order rows;
- OHLC invariants and non-finite values;
- volume and open-interest presence, units, resets, and publication cadence;
- contract rollover boundaries and whether prices were adjusted or left raw;
- row counts before/after each transformation.

Do not drop, deduplicate, forward-fill, resample, or repair rows without
recording the rule, affected count, and reason in the audit output.

### 4. Validate the `6E` ↔ `EURUSD` temporal join

Define the join key and tolerance before inspecting outcomes. Record timezone,
session filter, bar alignment, exact/as-of semantics, unmatched rows, duplicate
matches, tolerance violations, and any filtering by contract or rollover.

The join must be point-in-time safe: every field used at decision time `t` must
come from data available at or before `t`. Never use future bars, revised
statistics, or a full-sample label to repair a historical row. Never silently
substitute spot EURUSD for CME `6E`, or CME volume/open interest for another
instrument.

### 5. Certify reproducibility

Capture the content hash and byte size of every input, intermediate, and output
artifact. Also capture the manifest, generator script path, generator commit,
repository root, branch/ref, environment/package versions, and worktree state.

`CERTIFIED` requires a reproducible manifest and `worktree_state=CLEAN` for the
generator and audited artifacts. A dirty generator, missing log, unresolved
source identity, license ambiguity, hash mismatch, or unexplained row-count
difference is a blocking provenance failure; use a precise blocked state rather
than downgrading the requirement.

### 6. Produce an auditable result

Prefer existing repository contracts and audit writers. Emit machine-readable
JSON plus a concise Markdown summary when the project convention supports both.
The result must distinguish:

- `PASS`: all requested checks passed;
- `REVIEW`: evidence is present but a human decision or contract clarification
  remains;
- `BLOCKED`: a required provenance or reproducibility gate failed;
- `NOT_RUN`: a check was outside the authorized scope.

List every input/output path, hash, evidence reference, failed check, and next
action. Do not call a dataset certified merely because the row count matches.

## Tool boundaries

- Use Context7 only for version-specific API/library documentation.
- Use GitHub tooling only to inspect repository history, branches, commits, and
  review provenance when available; do not infer license rights from Git history.
- Use Engram for durable decisions and prior findings, not as a substitute for
  on-disk manifests or mission-state gates.
- Update Graphify after changing this skill or related project documentation;
  graph connectivity is useful context but is not data certification evidence.

## Stop conditions

Stop and report `BLOCKED` when the provider/license, instrument identity,
rollover, timestamp semantics, open-interest meaning, join rule, hash lineage,
generator commit, or worktree state cannot be established. Do not proceed to
backtest, training, OOS inference, or promotion to compensate for missing
provenance.
