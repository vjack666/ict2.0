# Optimización diagnóstica intradía Wyckoff + ICT

- **Estado:** `DIAGNOSTIC_OPTIMIZATION_COMPLETED`
- **Criterio:** menor `validation.log_loss`; empates por accuracy
- **Candidatos:** 12
- **Corpus SHA-256:** `7a610960d3035282db7a0e620b66c4312c66137c1b5f52ff3badab7237da9922`
- **TEST/OOS:** solo diagnóstico; no selección
- **HOLDOUT 2021–2025:** no leído

| # | Perfil | lr | l2 | Val accuracy | Val log-loss | Test/OOS accuracy | Seleccionado |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | ICT_ONLY | 0.0200 | 0.0001 | 0.398903 | 1.088969 | 0.403050 |  |
| 2 | ICT_ONLY | 0.0200 | 0.0010 | 0.398903 | 1.088967 | 0.403050 |  |
| 3 | ICT_ONLY | 0.0500 | 0.0001 | 0.398903 | 1.089249 | 0.403050 |  |
| 4 | ICT_ONLY | 0.0500 | 0.0010 | 0.398903 | 1.089246 | 0.403050 |  |
| 5 | WYCKOFF_ONLY | 0.0200 | 0.0001 | 0.397321 | 1.087695 | 0.400074 |  |
| 6 | WYCKOFF_ONLY | 0.0200 | 0.0010 | 0.397321 | 1.087695 | 0.400074 |  |
| 7 | WYCKOFF_ONLY | 0.0500 | 0.0001 | 0.397135 | 1.087901 | 0.400167 |  |
| 8 | WYCKOFF_ONLY | 0.0500 | 0.0010 | 0.397135 | 1.087901 | 0.400167 |  |
| 9 | WYCKOFF_ICT_COMBINED | 0.0200 | 0.0001 | 0.398810 | 1.087425 | 0.402492 |  |
| 10 | WYCKOFF_ICT_COMBINED | 0.0200 | 0.0010 | 0.398810 | 1.087424 | 0.402492 | SÍ |
| 11 | WYCKOFF_ICT_COMBINED | 0.0500 | 0.0001 | 0.398624 | 1.087645 | 0.402678 |  |
| 12 | WYCKOFF_ICT_COMBINED | 0.0500 | 0.0010 | 0.398624 | 1.087644 | 0.402585 |  |

## Dictamen

El ganador se seleccionó sin leer TEST/OOS ni HOLDOUT. Este resultado
sigue siendo diagnóstico y no demuestra edge, rentabilidad ni autoriza
`TRAINING_ELIGIBLE`, MT5 u órdenes.
