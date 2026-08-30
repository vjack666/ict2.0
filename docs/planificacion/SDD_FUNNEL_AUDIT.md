# SDD — Funnel Audit ICT FVG/OB

**Estado:** NORMATIVO — **A7 técnico COMPLETADO; fuente histórica fuera del alcance de certificación del Funnel (2026-08-29)**
**Fase:** Pre-backtest
**Código canónico:** `audits/codigo/funnel.py` (FunnelAudit A7 completo) y `audits/codigo/mtf_seq_funnel.py` (histórico)
**Runner A7:** `audits/codigo/mtf_seq_funnel_a7.py` (provenance técnica y de fuente separadas; fail-closed; NO sobrescribe histórico)
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

La corrida histórica que cerró este gate queda como evidencia versionada. Las futuras validaciones se ejecutan desde el checkout operativo local mediante las funciones canónicas; no se usa un destino remoto de ejecución.

### 5.2 Provenance técnica y límite de la fuente

El runner distingue explícitamente:

- `provenance_mechanical_ok`: los bytes de cada CSV coinciden con `SHA256SUMS`;
- `provenance_source`: metadata de proveedor, licencia, adquisición y ejecución,
  conservada como información descriptiva y de riesgo;
- `provenance_scope=TECHNICAL_FUNNEL_ONLY`: el alcance de A7;
- `a7_provenance_ok`/`provenance_ok`: bytes, hashes, metadata, configuración y
  commit del Funnel están enlazados;
- `certification_status`: `PASS` únicamente si auditoría técnica, provenance A7
  y PREFIX pasan.

La licencia o autorización del proveedor no forma parte del gate técnico A7 para
este snapshot histórico. `metadata.provenance.project_scope` lo clasifica como
`HISTORICAL_RESEARCH_FIXTURE_ONLY`: no es fuente operativa, no se usa en producción
y MT5 es la fuente objetivo para uso real. La metadata puede seguir mostrando
`license_and_permitted_use=UNKNOWN`; eso es una limitación de la fuente, no una
falla de causalidad del Funnel.

Un `aggregated_status=PASS` describe la auditoría de records del Funnel; no autoriza
por sí solo backtest, promoción ni trading. El cierre técnico A7 tampoco certifica
derechos legales de uso de los datos históricos.

El cierre de los doce objetivos se comprueba además con
`audits/codigo/a7_completion_audit.py`, que consume dos reportes independientes,
ejecuta la suite y persiste `reports/audits/experiments/fvg_ob/a7_completion_audit.json`.
Su código de salida es distinto de cero mientras cualquier OE obligatorio no sea
`PASS`; esto es una guarda de certificación, no una búsqueda de edge.

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

Artifact: `reports/audits/experiments/fvg_ob/mtf_seq_funnel.json`.

### 6.1 Cierre técnico A7

La auditoría independiente de completitud confirmó los doce objetivos `PASS`
con dos clean runs locales desde el commit `25d0e32`:

- `mtf_seq_funnel_a7_20260829_192637.json`;
- `mtf_seq_funnel_a7_20260829_200059.json`;
- `git_status=CLEAN` en ambos;
- `aggregated_status=PASS`, `findings=0`, `prefix_sequence_invariant=true`;
- checksum lógico idéntico: `321ce484e7b9a9458a00b324bd4377d5d50648872a1761de38e5913276c49a13`;
- suite completa: `375 passed`.

`OE-A7.9` certifica la provenance técnica exigida por A7: bytes, hashes,
metadata, configuración y commit. La autorización de la fuente histórica no
forma parte de este gate y permanece documentada como riesgo fuera de alcance.

Gate local: el auditor ejecutado desde el checkout operativo valida `status=COMPLETE`, PASS por TF, `causal_links == relation_count`, Sequence PASS y cobertura MTF mínima. No existe automatización remota vigente.

## 7. Estado del pre-backtest

El Funnel 20Y cerró técnicamente con provenance mecánica reproducible. La
revisión legal de la fuente histórica queda documentada fuera de A7 y no se reabre
salvo que el proyecto necesite certificar derechos de uso o realizar nuevas
adquisiciones. Eso **no** cierra A0-A9 ni TNA completo.

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
