# Análisis estadístico del baseline PROXY_PILOT — 2022–2025

## Bootstrap por clusters trimestrales

- Clusters temporales: 16 trimestres.
- Outcomes resueltos: 81.
- Media ponderada por trade: `-1,077566R`.
- Media de las medias trimestrales: `-0,978358R`.
- Bootstrap de clusters, 20.000 remuestras, semilla `20260902`:
  IC 95% aproximado `[-1,348208R, -0,604024R]`.
- Mínimo/máximo de medias trimestrales: `-2,612632R` / `+0,688480R`.

Cada remuestra toma trimestres completos, preservando la dependencia interna
de operaciones dentro del mismo trimestre. El resultado es descriptivo y no
pretende sustituir un contraste confirmatorio con el manifest definitivo.

## Dictamen estadístico

El intervalo clusterizado permanece completamente por debajo de cero: la
evidencia disponible contradice que el baseline tenga expectativa positiva
después de costes. No se declara todavía `NO_EDGE` global porque la fuente es
un proxy local, la cobertura no equivale al diseño completo 2006–2025 y la
procedencia del dataset intradía no está certificada de extremo a extremo.

**Estado:** `REVIEW` diagnóstico / `BLOCKED` certificación global.
