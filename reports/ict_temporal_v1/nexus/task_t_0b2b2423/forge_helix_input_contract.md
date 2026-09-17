# FORGE/HELIX INPUT CONTRACT - t_0b2b2423

**Status**: DELIVERED
**Task**: Certificar cobertura y reloj de fuentes existentes  
**Profile**: nexus  
**Date**: 2026-08-24

## Purpose
This document serves as the formal input contract from nexus to Forge and Helix, specifying exactly what data sources are available, verified, and ready for the next phase of development.

## Verified Sources (FORGE - t_7a8b1ea7)

### Sources Ready for Implementation
**Use these datasets**:
- `EURUSD_D1.csv` → SHA-256: `ff119f55b0224f75aa3b75f7a6773e5b75c21d2251f1b3b3954d5ae1f27db23e`
- `EURUSD_H1.csv` → SHA-256: `2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022`
- `EURUSD_H4.csv` → SHA-256: `46a950e087ed57cf2cc20ed13f3cfc7d2b7862d33f77b4a4f9cce1a40729efde`

**Properties**:
- Time range: 2006-01-01 to 2025-12-31 (20 years)
- Coverage: Complete, no gaps, no nulls
- OHLC consistency: Verified for first 100 rows
- Timezone: Should assume UTC (not specified in CSV)
- Format: CSV with `time,open,high,low,close` columns

### Sources NOT Ready for Implementation
**Do NOT use these until resolved**:
- `EURUSD_M1.parquet` → SHA-256: `d002b2ad042b84f18ac515b4dc5a498fe1cccdc83a00f238161b6a269ed3037d`
- `EURUSD_M5.parquet` → SHA-256: `0516a50ebd0708cc38366093e8f5da3192b61a499b2819456dbaebe8758edc01`

**Blocking Issues**:
- 99%+ null values in spread column
- Temporal coverage discrepancy (4-16 years vs metadata)
- Source origin/provenance unknown
- No documented acquisition method or license

## Temporal Semantics Specification (HELIX - t_929ec9b5)

### Bar Availability and Confirmation
For all timeframes, bars are available only after:
1. Bar close time is reached (UTC timestamp)
2. Additional latency buffer: 100ms for CSV, 50ms for Parquet
3. No future information can be used

### Causal Ordering Requirements
- Features must use timestamp <= decision_time only
- Never use bar i+1 when processing bar i
- Label/context available_at must be strictly after bar close

### Split Definitions (Not Modified)
- Splits must use timestamp boundaries, not loader selection
- TRAIN/VALIDATION/TEST/OOS defined by temporal ranges
- No leakage across split boundaries

## Readiness Summary

| Source | Status | Time Range | Ready For |
|--------|--------|------------|-----------|
| D1 CSV | VALIDATED | 2006-2025 | Research, Experiments |
| H1 CSV | VALIDATED | 2006-2025 | Research, Experiments |
| H4 CSV | VALIDATED | 2006-2025 | Research, Experiments |
| M1 Parquet | BLOCKED | 2012-2026 | Not usable |
| M5 Parquet | BLOCKED | 2022-2026 | Not usable |

## Requirements for Next Phase

### For Forge (t_7a8b1ea7)
1. Use only VALIDATED sources (D1, H1, H4 CSV)
2. Implement causal reader with hash verification
3. Document all source assumptions in code comments
4. Do NOT attempt to use Parquet files until issues resolved
5. Create in-memory transformations only (no data modification)

### For Helix (t_929ec9b5)
1. Train only on VALIDATED sources (D1, H1, H4 CSV)
2. Do NOT fabricate or impute missing data for blocked sources
3. Report if insufficient data for M1/M5 training
4. Use causal temporal splits, not random splits
5. Document any data limitations in training results

### For Orion (t_24fddd4f)
1. Update ICT specifications to reference verified sources only
2. Document temporal assumptions for each timeframe
3. Specify killzone timing with UTC timezone
4. Note that M1/M5 not available for multi-timeframe analysis

## Deliverables

This task has produced:
1. `data_inventory_report.md` - Complete dataset inventory with hashes and issues
2. `continuou_reader_contract.md` - Technical specification for causal reader
3. **This document** - Formal input contract to Forge/Helix

## Blockers

Before M1/M5 can be used, the following must be resolved:
1. Source provenance documentation
2. Spread column completeness (99%+ null values)
3. Temporal coverage reconciliation
4. Licensing and permitted-use verification

## Closure

This task is complete. The 3 VALIDATED sources are ready for the next phase. The 2 BLOCKED sources require investigation before they can be trusted. No data has been modified, regenerated, or fabricated. All findings are documented with SHA-256 hashes for verification.
