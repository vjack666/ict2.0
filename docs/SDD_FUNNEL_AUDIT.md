# SDD — Funnel Audit ICT FVG/OB

**Estado:** NORMATIVO
**Fase:** Pre-backtest
**Código canónico:** `audits/codigo/funnel.py`
**Bootstrap:** `audits/codigo/bootstrap.py`
**Propósito:** auditar la transformación causal de OHLC a candidatos ICT sin evaluar todavía rentabilidad.

## 1. Principio

El Funnel Audit es un instrumento de **falsificación estructural**, no un optimizador.

Debe poder contestar:

1. cuántos eventos entran en cada etapa;
2. cuántos sobreviven;
3. por qué se rechazan;
4. si las relaciones son causalmente válidas;
5. si la población se concentra anormalmente;
6. si el resultado es reproducible con el mismo snapshot.

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
CONFLUENCE
  ↓
VALID LINEAGE
  ↓
CANDIDATE SETUP
```

La etapa no puede consumir información de etapas posteriores.

## 3. Unidad de auditoría

La unidad primaria es un **evento confirmado**, no una operación.

Cada registro debe contener al menos:

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
- `pass_rate = accepted/input`;
- `reject_rate`;
- unique object count;
- duplicate count;
- orphan count;
- temporal violation count;
- per-direction counts;
- per-TF counts;
- per-OB-type counts cuando aplique;
- per-regime counts cuando exista régimen causalmente disponible.

No se usan PnL, win rate ni Sharpe como métricas del Funnel.

## 5. Reglas de calidad

### 5.1 Reproducibilidad
Mismo dataset + mismo commit + misma configuración → mismo reporte.

### 5.2 Truncation invariance
Para cualquier prefijo hasta `t`, ningún evento confirmado antes de `t` puede cambiar por añadir barras posteriores.

### 5.3 Temporalidad
`candidate <= confirmation <= tradable <= observation`.

### 5.4 Unicidad
Un mismo evento lógico no puede contarse varias veces por diferencias de representación.

### 5.5 Lineage
Un candidato debe poder rastrearse hasta sus padres sin ciclos ni enlaces futuros.

### 5.6 Explicabilidad de pérdidas
Toda reducción de población debe poder atribuirse a una regla explícita.

## 6. Arranque Hermes

`start_hermes.py` ejecuta el bootstrap de auditorías antes de habilitar cualquier fase. El bootstrap utiliza el contrato de "medianamente bueno": cero CRITICAL/HIGH, cero look-ahead y `audit_score >= 0.80`.

## 7. Segmentación obligatoria

Los reportes se segmentan por:

- bullish/bearish;
- H1/H4/D1 disponibles;
- año/mes;
- régimen de volatilidad si el régimen es anterior al evento;
- sesión cuando exista dato horario válido;
- tipo de OB implementado;
- combinación FVG/OB.

## 8. Señales de alarma

No se establece un umbral universal de "buen" funnel. Se generan `WARN` cuando aparece:

- colapso abrupto de una etapa;
- duplicación elevada;
- huérfanos elevados;
- concentración extrema en pocas fechas;
- diferencias inexplicadas entre bullish/bearish;
- diferencias inexplicadas entre TF;
- cambios de conteo al ampliar el dataset hacia el futuro;
- cambio de resultados con reordenamiento permitido equivalente.

Un `WARN` crítico requiere investigación antes del backtest.

## 9. Lo que el Funnel NO demuestra

El Funnel no demuestra edge, rentabilidad, Sharpe, drawdown ni supervivencia OOS. Sólo demuestra que la población que llegará al motor de ejecución está bien definida y auditada.

## 10. Dependencias

Funnel depende de A0-A6. Backtest depende del Funnel PASS y de una especificación de ejecución congelada.
