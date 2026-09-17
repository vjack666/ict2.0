# Contract for Causal Data Reader (Memory) - t_0b2b2423

**Status**: RESEARCH_READY
**Task**: t_0b2b2423 - Certificar cobertura y reloj de fuentes existentes
**Profile**: nexus (Data/Quality Department)
**Created**: 2026-08-24

## Purpose
Define a continuous causal reader architecture for ICT dataset consumption that does not confuse loader path issues with source absence.

## Key Principles (No Changes to Data)
- **Source Files Unmodified**: All verification performed in memory; no writes to `.hermes-cert/`
- **Hash Verification Mandatory**: Every dataset must match SHA-256 before processing
- **Causal Ordering**: All features must have timestamp <= decision_time
- **Available At**: Bars are only available after close time + latency buffer

## Source Classification

### Group 1: Certified CSV Sources (RESEARCH_READY)
1. `data/raw/EURUSD/EURUSD_D1.csv` (`VALIDATED`)
2. `data/raw/EURUSD/EURUSD_H1.csv` (`VALIDATED`)
3. `data/raw/EURUSD/EURUSD_H4.csv` (`VALIDATED`)

**Certification Requirements**:
- SHA-256 must match `datasets/eurusd_dukascopy_20y/SHA256SUMS`
- Metadata (`metadata.json`) claims verified
- No null values in OHLC
- Coverage: 2006-2025 (20 years per metadata)
- Timezone: Not specified (assumes UTC per plan recommendation)

### Group 2: Unverified Parquet Sources (BLOCKED)
1. `.hermes-cert/cert-branch/data/raw/EURUSD/EURUSD_M1.parquet`
2. `.hermes-cert/cert-branch/data/raw/EURUSD/EURUSD_M5.parquet`

**Blocking Issues**:
- Spread column 99%+ null values
- Coverage discrepancy: 4-16 years different from metadata
- Source origin unknown (no metadata or provenance docs)
- Requires investigation before use

## Temporal Semantics Specification

### Bar Availability Rules
For each bar at index `i`:
- **Available at**: `timestamp[i] + latency_buffer`
- **Latency buffer**: 100ms for CSV, 50ms for Parquet (recommended)
- **No future information**: Never use bar `i+1` data when processing bar `i`

### Split Definitions (For Reference Only - Not Modified)
- **TRAIN/VALIDATION/TEST/OOS splits**: Must be defined by timestamp ranges, not by loader selection
- **Split boundaries**: Must be aligned to calendar dates (not random selection)
- **No leakage**: Features must only use information up to split boundary timestamp

### Confirmation Requirements
For any dataset to be considered for experiments:
1. All OHLC columns complete (no nulls)
2. SHA-256 verified against manifest
3. Time coverage documented and verified
4. Timezone explicitly declared (UTC preferred)
5. Source provenance documented (vendor, license, acquisition method)
6. No temporal gaps > 1 day without documentation

## Continuous Reader Specification (Memory Only)

### Architecture
```
Source File → Hash Verification → In-Memory Buffer → Causal Filter → Feature Vector
```

### Implementation Requirements (Not Modifying Data)
1. Read dataset file into memory (not streaming)
2. Verify hash before processing
3. Build temporal index using timestamp column
4. Apply causal filter: only include bars with timestamp <= current_time
5. Generate features from verified bars only
6. Do not persist derived features back to source

### Error Handling
- If hash verification fails: Stop processing, return BLOCKED
- If temporal gaps detected: Document gap, continue with available data, mark as REVIEW
- If OHLC inconsistency detected: Stop processing, return BLOCKED
- If split contamination detected: Stop, return DATA_BLOCKED

## Next Action for Forge/Helix

This certification report provides input contract for:
- **Forge** (`t_7a8b1ea7`): Use verified CSV sources (D1, H1, H4) for implementation; avoid Parquet until resolved
- **Helix**: Only train on verified CSV sources; do not fabricate data for missing timeframes
- **Orion**: Update contract to reference verified sources only

**Blocker for Next Phase**: Parquet files must be resolved before M1/M5 timeframes can be used in multi-timeframe experiments.
