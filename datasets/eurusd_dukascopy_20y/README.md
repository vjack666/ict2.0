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
