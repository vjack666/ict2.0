# Auditoría Semántica SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1

**Fecha de auditoría:** 2026-09-16

## Resumen Ejecutivo

Este documento es el resultado de aplicar el detector semántico `SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1` a las 292 filas del dataset SETUP_GRAMMAR_DATASET_V1. El detector evalúa si cada PD Array (FVG/OB) cumple las tres condiciones de POI según la tesis ICT del proyecto (`21_POI.md` §16, `20_TESIS_ICT.md` §5b).

| Métrica | Valor |
|---------|-------|
| Filas auditadas | 292 |
| Filas originales NO_ZONE | 73 |
| Filas originales con zona | 219 |
| Filas EVIDENCE_MISSING | 0 |

### Estados Semánticos

- **VALID_ITF_ZONE:** 0 filas
- **INVALID_ZONE:** 292 filas
- **NO_ZONE:** 0 filas
- **EVIDENCE_MISSING:** 0 filas

## Análisis de las 73 Filas NO_ZONE Originales

Estas son las filas que el materializador actual etiquetó como `NO_ZONE`. La auditoría semántica determina si realmente no hay PD Array válido, o si hay un error de materialización.

| Índice | Split | Estado Semántico | Reason | h4_location | h1_alignment |
|--------|--------|-------------------|--------|-------------|---------------|
| 0 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 4 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 5 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 12 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 16 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 20 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 24 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 25 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 32 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 36 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 40 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 41 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 48 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 52 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | AGAINST |
| 53 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | AGAINST |
| 60 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 64 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 68 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 72 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 76 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 77 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 84 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 88 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 92 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 96 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 100 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 104 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | PREMIUM | AGAINST |
| 108 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 112 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 116 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 120 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 124 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 128 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 132 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 136 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 137 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 144 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 148 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 152 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 156 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 157 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 164 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 168 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | AGAINST |
| 169 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | AGAINST |
| 176 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 180 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 181 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 188 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 189 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 196 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 200 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 204 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | ALIGNED |
| 208 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 212 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 216 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 220 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 224 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | AGAINST |
| 225 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 232 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 233 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 240 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 244 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 248 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 252 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 253 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 260 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 264 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 268 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | PREMIUM | ALIGNED |
| 272 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 276 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 280 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 284 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 288 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |

### Resumen de las 73 NO_ZONE

- **VALID_ITF_ZONE:** 0
- **INVALID_ZONE:** 73
- **NO_ZONE:** 0
- **EVIDENCE_MISSING:** 0

### Falsos Negativos (NO_ZONE → VALID_ITF_ZONE)

No se encontraron falsos negativos hacia `VALID_ITF_ZONE`. Ninguna de las 73 filas originales etiquetadas como `NO_ZONE` resultó ser semánticamente un `VALID_ITF_ZONE`.

Esto sí prueba algo importante: **no hay zonas válidas escondidas dentro de las `NO_ZONE`**. Pero hay que tener cuidado con la interpretación: el auditor no encontró 73 `NO_ZONE` semánticas, encontró 73 `INVALID_ZONE` semánticas. Es decir, todas las que el materializador llamó "no zona" resultaron ser semánticamente zonas inválidas (tienen algún PD Array detectado, pero no cumplen las tres condiciones de POI del detector semántico), no ausencia pura de PD Array.

Por eso se habla de **0 falsos negativos hacia `VALID_ITF_ZONE`**, no de "73 NO_ZONE correctas" sin matiz.

## Análisis de las 219 Filas con Zona Original (USABLE_UNGRADED)

Estas son las filas que el materializador actual etiquetó como `USABLE_UNGRADED` (tienen PD Array). La auditoría semántica determina si realmente cumplen las tres condiciones de POI o si hay falsos positivos.

| Índice | Split | Estado Semántico | Reason | h4_location | h1_alignment |
|--------|--------|-------------------|--------|-------------|---------------|
| 1 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 2 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 3 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 6 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 7 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 8 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 9 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 10 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 11 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 13 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 14 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 15 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 17 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 18 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 19 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 21 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 22 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 23 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 26 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 27 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 28 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 29 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 30 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 31 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 33 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 34 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 35 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 37 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | ALIGNED |
| 38 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | ALIGNED |
| 39 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 42 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 43 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 44 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 45 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 46 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 47 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 49 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 50 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 51 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | ALIGNED |
| 54 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 55 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 56 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 57 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 58 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 59 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 61 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 62 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 63 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 65 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 66 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 67 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 69 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 70 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 71 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 73 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 74 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 75 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 78 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 79 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 80 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 81 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 82 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 83 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 85 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 86 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 87 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 89 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | ALIGNED |
| 90 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 91 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 93 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | ALIGNED |
| 94 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 95 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 97 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 98 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 99 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 101 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 102 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 103 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 105 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 106 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 107 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | PREMIUM | ALIGNED |
| 109 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 110 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | ALIGNED |
| 111 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | ALIGNED |
| 113 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 114 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 115 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 117 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 118 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 119 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 121 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 122 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 123 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 125 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 126 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 127 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 129 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 130 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 131 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 133 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 134 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 135 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 138 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 139 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 140 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 141 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 142 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 143 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 145 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 146 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | ALIGNED |
| 147 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | ALIGNED |
| 149 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 150 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 151 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 153 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 154 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 155 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 158 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 159 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 160 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 161 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 162 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 163 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 165 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 166 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 167 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 170 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 171 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 172 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | AGAINST |
| 173 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | AGAINST |
| 174 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | AGAINST |
| 175 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | AGAINST |
| 177 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 178 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 179 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 182 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 183 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 184 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 185 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 186 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 187 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 190 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 191 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 192 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 193 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 194 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 195 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 197 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 198 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 199 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 201 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 202 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 203 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 205 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | ALIGNED |
| 206 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | ALIGNED |
| 207 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | ALIGNED |
| 209 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 210 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 211 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 213 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 214 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 215 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 217 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 218 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | PREMIUM | ALIGNED |
| 219 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | PREMIUM | ALIGNED |
| 221 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 222 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 223 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 226 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 227 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 228 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 229 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 230 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 231 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 234 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 235 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 236 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 237 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 238 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | PREMIUM | ALIGNED |
| 239 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | PREMIUM | ALIGNED |
| 241 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 242 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 243 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | ALIGNED |
| 245 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | NEUTRAL |
| 246 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 247 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 249 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 250 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 251 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | DISCOUNT | NEUTRAL |
| 254 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 255 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | DISCOUNT | ALIGNED |
| 256 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 257 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 258 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 259 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 261 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 262 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 263 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b | DISCOUNT | AGAINST |
| 265 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 266 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 267 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D | EQUILIBRIUM | NEUTRAL |
| 269 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc | PREMIUM | ALIGNED |
| 270 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 271 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | ALIGNED |
| 273 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 274 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 275 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | AGAINST |
| 277 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 278 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 279 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | AGAINST |
| 281 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 282 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 283 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM | DISCOUNT | NEUTRAL |
| 285 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P | EQUILIBRIUM | NEUTRAL |
| 286 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 287 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b | PREMIUM | NEUTRAL |
| 289 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 290 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |
| 291 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO | PREMIUM | ALIGNED |

### Resumen de las 219 con Zona

- **VALID_ITF_ZONE:** 0
- **INVALID_ZONE:** 219
- **NO_ZONE:** 0
- **EVIDENCE_MISSING:** 0

### Falsos Positivos (Zona etiquetada como USABLE_UNGRADED pero semánticamente no válida)

**219 filas etiquetadas como USABLE_UNGRADED pero semánticamente NO son zonas válidas.**

| Índice | Split | Estado | Reason |
|--------|--------|--------|--------|
| 1 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 2 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 3 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 6 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 7 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 8 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 9 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 10 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 11 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 13 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 14 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 15 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 17 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 18 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 19 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 21 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 22 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 23 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 26 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 27 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 28 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 29 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 30 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 31 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 33 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 34 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 35 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 37 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 38 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 39 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 42 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 43 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 44 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 45 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 46 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 47 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 49 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 50 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 51 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 54 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 55 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 56 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 57 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 58 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 59 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 61 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 62 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 63 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 65 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 66 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 67 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 69 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 70 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 71 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 73 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 74 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 75 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 78 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 79 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 80 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 81 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 82 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 83 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 85 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 86 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 87 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 89 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 90 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 91 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 93 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 94 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 95 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 97 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 98 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 99 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 101 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 102 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 103 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 105 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 106 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 107 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 109 | TRAIN | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 110 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 111 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 113 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 114 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 115 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 117 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 118 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 119 | TRAIN | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 121 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 122 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 123 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 125 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 126 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 127 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 129 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 130 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 131 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 133 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 134 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 135 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 138 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 139 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 140 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 141 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 142 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 143 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 145 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 146 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 147 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 149 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 150 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 151 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 153 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 154 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 155 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 158 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 159 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 160 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 161 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 162 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 163 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 165 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 166 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 167 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 170 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 171 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 172 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 173 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 174 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 175 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 177 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 178 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 179 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 182 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 183 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 184 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 185 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 186 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 187 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 190 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 191 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 192 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 193 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 194 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 195 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 197 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 198 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 199 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 201 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 202 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 203 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 205 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 206 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 207 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 209 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b |
| 210 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 211 | VALIDATION | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 213 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 214 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 215 | VALIDATION | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 217 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 218 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 219 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 221 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b |
| 222 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 223 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 226 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 227 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 228 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 229 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 230 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 231 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 234 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 235 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 236 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 237 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 238 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 239 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 241 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 242 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 243 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 245 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 246 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 247 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 249 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 250 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 251 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 254 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 255 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 256 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 257 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 258 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 259 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 261 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b |
| 262 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b |
| 263 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=AGAINST: FAIL; context_b |
| 265 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 266 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 267 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera D |
| 269 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=ALIGNED: OK; context_buc |
| 270 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 271 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 273 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 274 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 275 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 277 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 278 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 279 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 281 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 282 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 283 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=DISCOUNT, se espera PREM |
| 285 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=EQUILIBRIUM, se espera P |
| 286 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 287 | TEST_OOS | INVALID_ZONE | sesgo HTF no alineado: h1_alignment=NEUTRAL: FAIL; context_b |
| 289 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 290 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |
| 291 | TEST_OOS | INVALID_ZONE | wrong-side: wrong-side: h4_location=PREMIUM, se espera DISCO |

## Distribución por Split

| Split | Total | NO_ZONE | USABLE_UNGRADED |
|-------|-------|---------|-----------------|
| TRAIN | 120 | 30 | 90 |
| VALIDATION | 96 | 24 | 72 |
| TEST_OOS | 76 | 19 | 57 |

## Conclusión

**Falsos negativos (NO_ZONE incorrectos):** 0 filas
**Falsos positivos (USABLE_UNGRADED incorrectos):** 219 filas
**EVIDENCE_MISSING (no se pudo auditar):** 0 filas


## Siguientes Pasos

1. Si hay EVIDENCE_MISSING > 0: corregir la materialización antes de continuar; no pueden participar en la auditoría semántica.
2. Si hay falsos negativos > 0: **corregir el materializador** `materialize_setup_grammar_dataset_v1.py` (no editar el dataset a mano) y regenerar el dataset desde las fuentes originales.
3. Si hay falsos positivos > 0: **corregir el materializador** para que no etiquete como USABLE_UNGRADED zonas que no cumplen las tres condiciones.
4. Si no hay errores (0 falsos negativos, 0 falsos positivos, 0 EVIDENCE_MISSING): las 292 etiquetas son semánticamente correctas según la tesis. **El materializador actual es correcto** para las tres condiciones de POI.
5. Regenerar el dataset corregido, verificar hashes, ejecutar pruebas y comparación antes/después.
6. Solo después: reentrenar `setup_quality_v1` comparado contra los baselines actuales.