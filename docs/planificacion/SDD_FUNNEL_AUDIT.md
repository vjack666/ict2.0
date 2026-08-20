# SDD — Funnel Audit ICT FVG/OB

**Estado:** NORMATIVO — **Funnel 20Y cerrado con gate CI**
**Fase:** Pre-backtest
**Código canónico:** `audits/codigo/funnel.py` y funciones de `audits/codigo/mtf_seq_funnel.py`
**Runner pesado versionado:** `scripts/grok_run_funnel_20y_full.py`
**Propósito:** auditar la transformación causal de OHLC a candidatos ICT sin evaluar todavía rentabilidad.

## 1. Principio

El Funnel Audit es un instrumento de **falsificación estructural e integridad de población**, no un optimizador.

Debe poder contestar:

1. cuántos eventos entran en cada etapa;
2. cuántos sobreviven;
3. por qué se rechazan;
4. si las relaciones son causalmente válidas;
5. si la población se concentra anormalmente;
6. si el resultado es reproducible con el mismo snapshot y configuración.

El Funnel **no demuestra edge, PnL ni win rate**.

## 2. Funnel canónico

```text
RAW BARS
  ↓
VALID BARS
  ↓
STRUCTURE
  ↓
BOS / CHOCH / MSS
  ↓
DISPLACEMENT
  ↓
FVG
  ↓
OB
  ↓
CONFLUENCE / RELATION
  ↓
VALID LINEAGE
  ↓
SEQUENCE / MTF NAVIGATION
```

La etapa no puede consumir información posterior a su timestamp de confirmación.

## 3. Unidad de auditoría

La unidad primaria es un **evento confirmado**, no una operación.

Cada registro debe conservar, cuando aplique:

- `audit_run_id`;
- dataset/version/hash;
- symbol;
- timeframe;
- observation bar/time;
- stage;
- object/event id;
- direction;
- parent ids;
- status (`accepted/rejected`);
- rejection reason;
- detector version;
- contract version.

## 4. Métricas

Para cada etapa:

- `input_count`;
- `accepted_count`;
- `rejected_count`;
- `pass_rate`;
- unique object count;
- duplicate count;
- orphan count;
- temporal violation count;
- per-direction/per-TF counts cuando estén disponibles;
- lineage y causal links.

No se usan PnL, win rate ni Sharpe como métricas del Funnel.

## 5. Reglas de calidad

### 5.1 Reproducibilidad

Mismo dataset + mismo commit + misma configuración → mismo reporte, salvo campos explícitamente no deterministas como timestamp de generación.

La corrida 20Y que cerró este gate fue ejecutada en Grok mediante `scripts/grok_run_funnel_20y_full.py`, que orquesta las funciones canónicas. El módulo `audits/codigo/mtf_seq_funnel.py` no debe confundirse con ese orquestador.

### 5.2 Truncation invariance

Para cualquier prefijo hasta `t`, ningún evento confirmado antes de `t` puede cambiar por añadir barras posteriores.

### 5.3 Temporalidad

Los timestamps de candidate/confirmation/tradable/observation deben respetar el contrato temporal del objeto. Ningún enlace causal puede apuntar hacia el futuro.

### 5.4 Unicidad

Un mismo evento lógico no puede contarse varias veces por diferencias de representación.

### 5.5 Lineage

Un candidato debe poder rastrearse hasta sus padres sin ciclos ni enlaces futuros.

### 5.6 Explicabilidad

Toda reducción de población debe poder atribuirse a una regla explícita.

## 6. Resultado 20Y cerrado

Dataset: **Dukascopy EURUSD 20Y (2006–2025)**.

| TF | FVG | OB | Relaciones | Causal links | Estado |
|---|---:|---:|---:|---:|---|
| H1 | 22477 | 2799 | 702 | 702 | PASS |
| H4 | 6497 | 862 | 206 | 206 | PASS |
| D1 | 1543 | 214 | 58 | 58 | PASS |

Sequence H1: **1460 cadenas, 3 COMPLETE**. La población COMPLETE sigue siendo insuficiente para declarar edge.

MTF dense: **1239 samples, `sample_every=100`, `ok_rate=1.0`**, interpretado como integridad de navegación, no win rate.

Artifact: `reports/audits/mtf_seq_funnel.json`.

Gate CI: `.github/workflows/hermes-fvg-ob-funnel.yml` valida `status=COMPLETE`, PASS por TF, `causal_links == relation_count`, Sequence PASS y cobertura MTF mínima.

## 7. Estado del pre-backtest

El Funnel 20Y está cerrado. Eso **no** cierra A0-A9 ni TNA completo.

La habilitación del backtest sigue condicionada a la pila pre-backtest vigente y a una especificación de ejecución congelada.

## 8. Señales de alarma

No existe un umbral universal de “buen funnel”. Se generan WARN cuando aparece:

- colapso abrupto de una etapa;
- duplicación elevada;
- huérfanos elevados;
- concentración extrema en pocas fechas;
- diferencias inexplicadas entre bullish/bearish o TF;
- cambios de conteo al ampliar el dataset hacia el futuro;
- cambios con reordenamiento equivalente permitido.

Un WARN crítico requiere investigación antes del backtest.

## 9. Lo que el Funnel NO demuestra

El Funnel no demuestra edge, rentabilidad, Sharpe, drawdown, supervivencia OOS ni calidad de entrada. Demuestra que la población estructural/lineage/navegación auditada cumple sus invariantes.

## 10. Dependencias

El Funnel depende de los contratos y auditorías estructurales previos. El backtest depende de Funnel PASS **más** la pila pre-backtest/TNA aceptable y una especificación de ejecución congelada.
