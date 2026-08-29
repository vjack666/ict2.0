# EURUSD Dukascopy 20Y (2006-01-01 → 2025-12-31)

Bid OHLC for cloud/CI runs. **Not** MT5 of the Director.

| File | TF | Rows (approx) |
| ------ | ----- | --------------- |
| EURUSD_H1.csv | H1 | 124377 |
| EURUSD_H4.csv | H4 | 32133 |
| EURUSD_D1.csv | D1 | 6258 |

Columns: `time,open,high,low,close`

Source: `npx dukascopy-node -i eurusd -from 2006-01-01 -to 2026-01-01 -t {h1|h4|d1} -f csv`

To restore into runtime path:

```bash
mkdir -p data/raw/EURUSD
cp datasets/eurusd_dukascopy_20y/EURUSD_*.csv data/raw/EURUSD/
```

Verify: `sha256sum -c SHA256SUMS`

## Provenance boundary (CDO audit 2026-08-29)

This is a versioned EURUSD spot/bid snapshot from Dukascopy, not CME 6E and
not an open-interest source. The A7 runner hashes the raw bytes it loads.
The repository now fixes LF for this snapshot in `.gitattributes`; this
overrides Windows `core.autocrlf=true`, so clean Windows checkouts and the Git
blob expose the same CSV bytes. `SHA256SUMS` contains the resulting LF hashes.

The CSV values were not changed; only CRLF line endings were normalized to LF.
The hash gate is PASS for this snapshot. Overall A7 provenance remains
BLOCKED until source license/acquisition evidence and a clean A7 generator
run are independently established. The inspected report
`mtf_seq_funnel_a7_20260829_115117.json` predates this LF correction and was
not rewritten; it remains historical evidence with `git_status=DIRTY`. This
does not certify the dataset or Funnel A7.
