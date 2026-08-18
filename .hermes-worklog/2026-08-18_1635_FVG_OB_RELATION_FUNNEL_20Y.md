# Bitácora — Funnel FVG/OB + Relación sobre 20Y

**Fecha:** 2026-08-18 16:35 UTC-5  
**Base código:** 95b48b4 (relation integration)  
**Data:** Dukascopy EURUSD 2006–2025

## Resultados
| TF | FVG | OB | Relations | rate vs FVG | rate vs OB |
|----|----:|---:|----------:|------------:|-----------:|
| H1 | 22477 | 2799 | 2318 | 10.3% | 82.8% |
| H4 | 6497 | 862 | 716 | 11.0% | 83.1% |
| D1 | 1543 | 214 | 178 | 11.5% | 83.2% |

CausalLinks = relation_count en los 3 TF. Audit PASS.

## Data en repo
`datasets/eurusd_dukascopy_20y/` (CSV + SHA256) para corridas en nube.
Script regeneración: `tools/data/acquire_eurusd_20y.sh`
