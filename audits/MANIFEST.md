# Audit Subsystem Manifest

**CI verification:** required before declaring any audit Gate complete.

## Canonical executable location

All executable audit code lives under:

```text
/audits/codigo/
```

There must be no second executable audit implementation outside this folder.

## Implemented

- A0: `audits/codigo/data_integrity.py` + `audits/codigo/full_stack.py`
- A1: `audits/codigo/full_stack.py`
- A2: `audits/codigo/temporal.py` + `audits/codigo/full_stack.py`
- A3-A6: `audits/codigo/audit_stack.py` + `audits/codigo/full_stack.py`
- A7: `audits/codigo/funnel.py` + `audits/codigo/full_stack.py`
- A8-A9: `audits/codigo/full_stack.py`
- Shared Gate contract: `audits/codigo/gate.py`
- Mandatory bootstrap: `audits/codigo/bootstrap.py`
- Contract tests: `tests/test_audit_subsystem.py`

## Startup contract

`start_hermes.py` is the mandatory local entrypoint. Its first operation is always the audit bootstrap.

The bootstrap loops:

`AUDIT → FINDINGS → FIX COMMAND → TEST → AUDIT`

until the configured "medianamente bueno" threshold is reached or the iteration limit is exhausted.

## Full-stack evidence

`python -m audits.codigo.run_full_stack --scope real` validates the versioned
Dukascopy snapshot and the versioned real Funnel/TNA artifacts without PnL,
entries, downloads, or dataset mutation. The smoke runner remains available via
`--scope smoke` for unit tests.

## Rule

The existence of code does not imply Gate PASS. Every audit requires CI evidence and a synchronized worklog.
