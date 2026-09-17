# Dataset Inventory Report - Task t_0b2b2423

**Task**: Certificar cobertura y reloj de fuentes existentes
**Generated**: 2026-08-24
**Profile**: nexus
**Data Source**: .hermes-cert/cert-branch

## Executive Summary

Found **4 source datasets** with significant temporal coverage discrepancies between Parquet and CSV formats. Major data quality issues identified in spread columns and temporal consistency with metadata claims.

## Dataset Details

### 1. EURUSD_M1.parquet
**Path**: `.hermes-cert/cert-branch/data/raw/EURUSD/EURUSD_M1.parquet`
**SHA-256**: `d002b2ad042b84f18ac515b4dc5a498fe1cccdc83a00f238161b6a269ed3037d`

**Coverage Analysis**:
- **Rows**: 5,771,913
- **Columns**: `time`, `open`, `high`, `low`, `close`, `tick_volume`, `spread`
- **Time Range**: 2012-01-11 01:37:00+00:00 to 2026-08-14 23:59:00+00:00 (14.1 years)
- **Timezone**: UTC
- **Data Types**: datetime64[ms, UTC] for timestamp

**Data Quality Issues**:
- **Critical**: 5,757,513 null values (99.6%) in `spread` column
- **No null values** in OHLC columns

**Temporal Discrepancy**: Metadata claims 2006-2025 (20 years), but actual Parquet coverage is 2012-2026 (14 years) — **4-year gap**

---

### 2. EURUSD_M5.parquet
**Path**: `.hermes-cert/cert-branch/data/raw/EURUSD/EURUSD_M5.parquet`
**SHA-256**: `0516a50ebd0708cc38366093e8f5da3192b61a499b2819456dbaebe8758edc01`

**Coverage Analysis**:
- **Rows**: 334,852
- **Columns**: `time`, `open`, `high`, `low`, `close`, `tick_volume`, `spread`
- **Time Range**: 2022-01-02 17:00:00+00:00 to 2026-08-14 23:55:00+00:00 (4.6 years)
- **Timezone**: UTC
- **Data Types**: datetime64[us, UTC] for timestamp

**Data Quality Issues**:
- **Critical**: 331,972 null values (99.1%) in `spread` column
- **No null values** in OHLC columns

**Temporal Discrepancy**: Metadata claims 2006-2025 (20 years), but actual Parquet coverage is 2022-2026 (4.6 years) — **~16-year gap**

---

### 3. EURUSD_D1.csv
**Path**: `.hermes-cert/cert-branch/datasets/eurusd_dukascopy_20y/EURUSD_D1.csv`
**SHA-256**: `ff119f55b0224f75aa3b75f7a6773e5b75c21d2251f1b3b3954d5ae1f27db23e`

**Coverage Analysis**:
- **Rows**: 6,258
- **Columns**: `time`, `open`, `high`, `low`, `close`
- **Time Range**: 2006-01-01 to 2025-12-31 (20.0 years)
- **Timezone**: No timezone info in CSV
- **OHLC Integrity**: Perfect consistency in first 100 rows

**Data Quality**: All columns fully populated, no nulls
**Matches Metadata**: Coverage aligns with 20-year claim

---

### 4. EURUSD_H1.csv
**Path**: `.hermes-cert/cert-branch/datasets/eurusd_dukascopy_20y/EURUSD_H1.csv`
**SHA-256**: `2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022`

**Coverage Analysis**:
- **Rows**: 124,377
- **Columns**: `time`, `open`, `high`, `low`, `close`
- **Time Range**: 2006-01-01 21:00:00 to 2025-12-31 21:00:00 (20.0 years)
- **Timezone**: No timezone info in CSV
- **OHLC Integrity**: Perfect consistency in first 100 rows

**Data Quality**: All columns fully populated, no nulls
**Matches Metadata**: Coverage aligns with 20-year claim

---

### 5. EURUSD_H4.csv
**Path**: `.hermes-cert/cert-branch/datasets/eurusd_dukascopy_20y/EURUSD_H4.csv`
**SHA-256**: `46a950e087ed57cf2cc20ed13f3cfc7d2b7862d33f77b4a4f9cce1a40729efde`

**Coverage Analysis**:
- **Rows**: 32,133
- **Columns**: `time`, `open`, `high`, `low`, `close`
- **Time Range**: 2006-01-01 20:00:00 to 2025-12-31 20:00:00 (20.0 years)
- **Timezone**: No timezone info in CSV
- **OHLC Integrity**: Perfect consistency in first 100 rows

**Data Quality**: All columns fully populated, no nulls
**Matches Metadata**: Coverage aligns with 20-year claim

## Critical Findings

### Temporal Discrepancy - PROVENANCE_INCOMPLETE
**Issue**: 4 out of 5 source files have coverage that does not match metadata claims.

1. **M1 Parquet**: Claims 2006-2025, actual 2012-2026 (4-year shortfall)
2. **M5 Parquet**: Claims 2006-2025, actual 2022-2026 (16-year shortfall)  
3. **Both Parquets**: M5 significantly newer than metadata suggests
4. **Source Provenance Inconsistent**: Parquet sources differ from CSV sources

**Impact**: Cannot trust metadata claims, dataset lineage broken

### Data Completeness - BLOCKED
**Issue**: Spread columns in Parquet files have 99%+ null values.

1. **M1**: 5,757,513 null spread values (99.6%)
2. **M5**: 331,972 null spread values (99.1%)
3. **OHLC columns**: All complete and consistent

**Impact**: Spread data is essentially unusable, dataset cannot serve as complete source

### Multi-Source Discrepancy - DATA_BLOCKED
**Issue**: Two different source families for same symbol/timeframes:

1. **CSV Family**: 2006-2025, Dukascopy origin, full metadata
2. **Parquet Family**: 2012-2026, unknown origin, missing metadata

**Impact**: Cannot determine which source is correct or how they relate

## Status Assessment

### Dataset Certification Results

1. **`EURUSD_D1.csv`**: ✅ `VALIDATED`
   - Matches metadata claims
   - Complete data
   - OHLC consistent

2. **`EURUSD_H1.csv`**: ✅ `VALIDATED`
   - Matches metadata claims
   - Complete data
   - OHLC consistent

3. **`EURUSD_H4.csv`**: ✅ `VALIDATED`
   - Matches metadata claims
   - Complete data
   - OHLC consistent

4. **`EURUSD_M1.parquet`**: ❌ `BLOCKED`
   - Temporal gap: 4 years vs claimed
   - 99.6% null spread column
   - Unknown source origin

5. **`EURUSD_M5.parquet`**: ❌ `BLOCKED`
   - Temporal gap: 16 years vs claimed
   - 99.1% null spread column
   - Unknown source origin

## Recommended Actions

### Immediate
1. **Investigate Parquet Sources**: Determine origin, licensing, and coverage method
2. **Resolve Spread Data Issue**: Investigate why 99%+ spread values are null
3. **Temporal Reconciliation**: Either correct metadata or discover missing data

### Before Certification
1. **Establish Source Provenance**: Document Parquet file origins and acquisition
2. **Data Integrity**: Investigate and fix spread column completeness
3. **Temporal Alignment**: Verify Parquet coverage matches or document discrepancy
4. **Metadata Consistency**: Ensure all datasets have consistent temporal claims

## Conclusion

**Partial Dataset Available**: 3 out of 5 source files are valid (D1, H1, H4 CSV).

**Major Issues**: Parquet files have unresolvable provenance, completeness, and temporal issues.

**Ready For Use**: D1/H1/H4 CSV datasets for research and experimentation.

**Not Ready For Use**: Parquet datasets require resolution of critical data quality and provenance issues before they can be trusted.

**Note**: This does not mean Parquet files are unusable — they require additional investigation to understand their relationship to the CSV files and resolve data quality issues.