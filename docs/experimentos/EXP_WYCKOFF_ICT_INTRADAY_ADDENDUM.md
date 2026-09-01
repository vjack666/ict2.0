# Addendum — EXP-WYCKOFF-ICT-01 intradía H1→M15

**Estado:** PRE-REGISTRADO PARA DIAGNÓSTICO LOCAL
**Extiende:** `docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md`
**SDD de IA:** `docs/planificacion/SDD_AI_OUTCOME_CLASSIFIER_V1.md`
**Modo:** `LOCAL_ONLY`
**can_trade:** `false`

## Motivo del addendum

El preregistro original estudia Wyckoff en H1/H4/D1 y prohíbe entrenar IA.
Este addendum es necesario porque la pregunta nueva cambia la unidad temporal:
Wyckoff H1 como campaña, Wyckoff M15 como evento y ICT M15 como confirmación.
No modifica retroactivamente el experimento original ni sus resultados.

## Universo y datos

- Instrumento: EURUSD spot bid de Dukascopy, solo investigación histórica.
- Primer bloque: 2006-01-01 hasta 2010-12-31.
- Datos requeridos: H1 histórico canónico y M15 histórico separado en
  `datasets/eurusd_dukascopy_intraday_2006_2010/`.
- MT5 `data/raw/*.parquet` queda fuera del entrenamiento y no completa huecos.
- El campo `volume` de M15 se conserva como volumen del proveedor; su semántica
  debe permanecer explícita y no se interpreta como volumen centralizado.

## Arquitectura temporal congelada

```text
D1/H4 (contexto existente, si está disponible)
        ↓
H1 (rango y fase Wyckoff)
        ↓
M15 (evento Wyckoff + confirmación ICT)
        ↓
outcome futuro a +12 velas M15 (3 horas)
        ↓
clasificador determinista diagnóstico
```

Las features se calculan únicamente con barras cerradas hasta `event_time`.
Wyckoff aporta `phase` y eventos H1/M15; ICT aporta BOS, CHOCH, displacement,
FVG y sweep observados en M15. Ninguna etiqueta, outcome, PnL, entry, SL o TP
puede entrar en `features_at_t`.

## Etiqueta congelada

Para una dirección ICT observada en M15 se calcula el movimiento del close a
`+12` barras. La escala es la mediana del rango OHLC de las 20 barras previas:

- `continuation`: movimiento firmado `>= 1.0 × escala`.
- `reversal`: movimiento firmado `<= -1.0 × escala`.
- `failure`: cualquier otro resultado.

Esta etiqueta es diagnóstica y no es una señal ni una autorización operativa.

## Comparaciones

El primer artefacto reportará el perfil combinado Wyckoff+ICT. La comparación
científica posterior deberá separar:

1. ICT M15 sin features Wyckoff.
2. Wyckoff H1/M15 sin features ICT.
3. Wyckoff H1/M15 + ICT M15.

El bloque 2021-2025 será HOLDOUT cronológico y no se usará para ajustar el
primer modelo de 2006-2010.

## Gates y salida

El primer resultado solo puede ser `DIAGNOSTIC_ONLY_COMPLETED` o `BLOCKED`.
Debe incluir hashes de datos y JSONL, conteos de clases, split temporal,
`fit_executed`, métricas TRAIN/VALIDATION/TEST-OOS y `can_trade=false`.
No puede declarar `TRAINING_ELIGIBLE`, certificación científica, edge,
promoción, Shadow MT5 ni órdenes. La certificación de provenance y la revisión
independiente se mantienen como gates separados.

## Ejecución comparativa 2026-09-01

Se ejecutaron tres perfiles sobre el mismo JSONL causal de 2006–2010, con la
misma semilla, etiqueta `label_end_12`, algoritmo y split temporal 60/20/20:

1. `ICT_ONLY`: señales ICT M15 y contexto direccional básico.
2. `WYCKOFF_ONLY`: fases/eventos Wyckoff H1/M15 y contexto direccional básico.
3. `WYCKOFF_ICT_COMBINED`: ambos perfiles.

La salida es comparativa y diagnóstica. El TEST/OOS no se utilizó para ajustar
ninguna variante, el HOLDOUT 2021–2025 no se tocó y todas mantienen
`can_trade=false`. La interpretación científica queda en `REVIEW`: las
diferencias observadas no son suficientes para declarar edge ni superioridad
robusta.
