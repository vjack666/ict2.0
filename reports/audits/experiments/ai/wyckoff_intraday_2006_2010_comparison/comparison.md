# Comparación diagnóstica ICT-only vs Wyckoff-only vs combinado

- **Estado:** `DIAGNOSTIC_COMPARISON_COMPLETED`
- **Corpus:** `C:\Users\v_jac\Desktop\ICT SYSTEM\reports\audits\experiments\ai\wyckoff_intraday_2006_2010.jsonl`
- **Filas:** 53761
- **Hash corpus:** `7a610960d3035282db7a0e620b66c4312c66137c1b5f52ff3badab7237da9922`
- **Etiqueta:** `label_end_12`
- **Modo:** `DIAGNOSTIC_ONLY`; `can_trade=false`; sin promoción

## Métricas

| Variante | Features | Train acc. | Validation acc. | Test/OOS acc. | Test/OOS log-loss | Δ vs mayoría |
|---|---:|---:|---:|---:|---:|---:|
| ICT_ONLY | 12 | 0.428664 | 0.398903 | 0.403050 | 1.090154 | +0.004092 |
| WYCKOFF_ONLY | 38 | 0.426277 | 0.397135 | 0.400167 | 1.090933 | +0.001209 |
| WYCKOFF_ICT_COMBINED | 48 | 0.428912 | 0.398624 | 0.402678 | 1.090112 | +0.003720 |

## Lectura

La tabla solo permite comparar el aporte incremental de cada perfil.
No demuestra edge ni rentabilidad. El TEST/OOS permanece fuera del ajuste;
el holdout cronológico 2021–2025 sigue reservado para una fase posterior.

## Controles

- Mismo JSONL, hash de entrada y etiqueta para las tres variantes.
- Mismo split temporal 60/20/20, semilla y algoritmo determinista.
- Sin `DatasetSnapshot` certificado, sin `ModelRegistry`, sin MT5 y sin órdenes.
- Provenance/licencia histórica permanece en `REVIEW/BLOCKED` hasta resolverla.
