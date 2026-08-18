# Audit Subsystem Manifest

**CI verification:** required before declaring any audit Gate complete.

## Canonical executable location

All executable audit code lives under:

```text
/audits/codigo/
```

There must be no second executable audit implementation outside this folder.

## Implemented

- A0: `audits/codigo/data_integrity.py`
- A2: `audits/codigo/temporal.py`
- A7: `audits/codigo/funnel.py`
- Shared Gate contract: `audits/codigo/gate.py`
- Mandatory bootstrap: `audits/codigo/bootstrap.py`
- Contract tests: `tests/test_audit_subsystem.py`

## Startup contract

`start_hermes.py` is the mandatory local entrypoint. Its first operation is always the audit bootstrap.

The bootstrap loops:

`AUDIT → FINDINGS → FIX COMMAND → TEST → AUDIT`

until the configured "medianamente bueno" threshold is reached or the iteration limit is exhausted.

## Pending implementations

A1, A3, A4, A5, A6, A8 and A9 remain contract-defined and must receive dedicated executable checks before their Gates can close.

## Rule

The existence of code does not imply Gate PASS. Every audit requires CI evidence and a synchronized worklog.
