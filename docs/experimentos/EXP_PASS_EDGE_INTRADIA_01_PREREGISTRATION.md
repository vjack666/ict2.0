# Preregistro — EXP-PASS-EDGE-INTRADIA-01

**Fecha:** 2026-09-02

**Estado:** `DRAFT_BLOCKED / NO EJECUTAR`

**Modo:** `LOCAL_ONLY`

**Owner:** D5 Assurance / CRO, con revisión D4 Datos y D6 Research

**Contrato:** `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md`

## 1. Propósito y no-objetivos

Este documento pre-registra una futura evaluación del **baseline económico
intradía sin IA**. La pregunta es si la especificación ICT congelada produce
expectativa media `net_R` materialmente positiva después de costes, frente al
baseline nulo `R0=0`.

Este preregistro no declara edge, no autoriza ejecución, no selecciona datos,
no entrena IA, no crea señales operativas y no autoriza MT5, broker, órdenes o
promoción. El estado actual es `DRAFT_BLOCKED / NO EJECUTAR` porque faltan
evidencias económicas y de provenance requeridas en §8.

## 2. Autoridad y especificación seleccionada

La autoridad documental es el contrato `CONTRATO_PASS_EDGE_INTRADIA_V1.md` y la
tesis ICT, especialmente:

- `docs/ict/15_INTRADIA_ENTRADA_SL_TP.md`;
- `docs/ict/16_TEMPORALIDAD_EJECUCION.md`;
- `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`;
- `docs/ict/SPEC_TESIS_FORMAL.md`.

La especificación candidata, sin modificarla durante esta misión, es:

```text
context_htf (H4)
    → OB (M15)
    → FVG (M15)
    → BOS (M15)
    → displacement (M15)
    → entry en el retorno a la zona FVG/OB (M15 EXEC)
```

`M15` es el timeframe de ejecución: entry, SL y TP económicos deben resolverse
en M15. La confirmación de sweep/reclaim/failure y la prioridad exacta de
entrada forman parte de la evidencia ICT que debe quedar visible en el setup;
si su semántica o el fill económico no puede resolverse punto-en-tiempo, el
setup se rechaza o el experimento queda `BLOCKED`.

No se introduce otra FSM, otro detector, otra autoridad ni ninguna feature de
IA. La especificación no se optimiza con DESIGN, VALIDATION ni HOLDOUT.

## 3. Pregunta y hipótesis económica

Pregunta confirmatoria:

> ¿La unidad setup producida por la cadena H4→M15 anterior tiene
> `E[net_R] > 0` y alcanza el MDE económico preregistrado después de todos los
> costes observables y reproducibles?

```text
H0: E[net_R] <= 0
H1: E[net_R] > 0
baseline nulo: R0 = 0 net_R por setup
MDE primario: +0,10R por setup independiente
alpha primario: 0,05 unilateral
potencia objetivo: 0,80
```

Accuracy, log-loss, `label_end_6`, `label_end_12`, win rate aislado, conteos de
clases o una mejora de clasificación no prueban esta hipótesis.

## 4. Unidad de análisis y deduplicación

Una observación es un único setup económico canónico con:

- `setup_id` estable;
- `decision_time` y `entry_time` observables;
- `context_htf`, OB, FVG, BOS y displacement con lineage;
- dirección, símbolo, venue y timeframe;
- regla de entry, SL, TP/exit y riesgo inicial `R`;
- `episode_id` o `chain_id` para dependencia estadística.

La unidad inferencial es el setup, pero el bootstrap se agrupa por episodio o
cadena. No se cuentan como observaciones independientes las reentradas, las
variantes de la misma decisión, las barras duplicadas ni los derivados de un
mismo episodio. Un `setup_id` duplicado, `R=0`, timestamp ausente o lineage
incompleto produce `BLOCKED`.

## 5. Outcome económico y campos que deben congelarse

El outcome será:

```text
net_R = (gross_pnl_cash - spread - commission - slippage
         - financing - otros costes preregistrados) / initial_risk_cash
```

Antes de ejecutar deben quedar congelados:

1. precio y momento del fill económico;
2. definición de `R` y buffer del SL;
3. precio, prioridad y disponibilidad de TP/SL;
4. tratamiento de gaps y toque simultáneo TP/SL;
5. cierre parcial, timeout, financiación y conversión monetaria;
6. spread, comisión y slippage por sesión/condición;
7. timezone, frontera de vela, calendario y sesiones.

El contrato ICT respalda la entrada en retorno a FVG/OB, pero el **fill
económico M15** está actualmente `UNKNOWN/BLOCKED`. También están
`UNKNOWN/BLOCKED` el spread, comisión, slippage M15 y el horizonte económico
final. No se asume coste cero, fill al close ni horizonte elegido post-hoc.

El horizonte futuro debe ser uno de `FIXED_BARS`, `SESSION_CLOSE` o
`FIRST_TOUCH_TIMEOUT`, con parámetros completos pre-registrados antes de la
ejecución. Hasta entonces el gate económico es `BLOCKED`.

## 6. Particiones temporales congeladas

Las ventanas son UTC y tienen límite final exclusivo:

| Partición | Ventana | Uso |
|---|---|---|
| `DESIGN` | `[2006-01-01, 2016-01-01)` | congelar y verificar la mecánica; no seleccionar edge post-hoc |
| `VALIDATION` | `[2016-01-01, 2021-01-01)` | estabilidad de la especificación congelada |
| `HOLDOUT` | `[2021-01-01, 2026-01-01)` | evaluación confirmatoria final, una sola lectura |

El HOLDOUT no puede seleccionar filtros, parámetros, sesiones, regímenes,
costes, horizonte, TP, SL, entry ni reglas. Warmup, si fuese indispensable,
debe estar separado, documentado y no puede aportar outcomes ni información
futura al setup.

## 7. Inferencia, potencia y estabilidad

La evaluación futura debe calcular `n_required` sobre clusters independientes,
con supuestos de varianza e ICC documentados. `n>=30` no sustituye la potencia.

El IC primario será unilateral del 95% para la media de `net_R`, con bootstrap
por `episode_id`/`chain_id`, mínimo 10.000 réplicas, semilla fija y método para
clusters pequeños congelado antes de correr. Se reportará además IC bilateral
del 95%, media, mediana, desviación, cuantiles, número de setups y clusters.

Debe existir desglose obligatorio por:

- partición y año;
- sesión UTC preregistrada;
- régimen causal preregistrado, incluyendo tendencia/rango y volatilidad
  calculada solo hasta `decision_time`.

La definición exacta de sesiones, régimen, costes por sesión y umbral de
estabilidad sigue `UNKNOWN/BLOCKED` hasta completar el preregistro económico
ejecutable. La familia secundaria usará Holm-Bonferroni (o Bonferroni) con
alfa familiar `0,05`; las lecturas adicionales serán `EXPLORATORY`.

## 8. Gates y bloqueadores actuales

La futura ejecución debe producir `PASS` en todos los gates duros:

| Gate | Criterio | Estado actual |
|---|---|---|
| `SPEC_FREEZE` | cadena H4→M15 congelada y sin selección post-hoc | `PASS_DOCUMENTAL` |
| `UNIT_IDENTITY` | setup único, `setup_id`, episodio y `R` resolubles | `UNKNOWN/BLOCKED` |
| `ECONOMIC_FILL` | fill M15 determinista y observable | `UNKNOWN/BLOCKED` |
| `COSTS` | spread/comisión/slippage/financiación M15 documentados | `UNKNOWN/BLOCKED` |
| `HORIZON_EXIT` | salida y horizonte final congelados | `UNKNOWN/BLOCKED` |
| `PIT_CAUSAL` | features visibles en `decision_time`, outcome posterior | `PENDING` |
| `FULL_PREFIX` | igualdad causal en todos los cortes requeridos | `PENDING` |
| `POWER_MDE` | `+0,10R`, potencia `0,80`, clusters suficientes | `PENDING` |
| `STABILITY` | periodo, sesión y régimen sin inestabilidad material | `PENDING` |
| `PROVENANCE` | fuente, licencia, adquisición, manifest, hashes y lineage completos | `BLOCKED` |
| `REPRODUCIBILITY` | manifest completo, commits resolubles y worktree limpio | `BLOCKED` |
| `AUTHORIZATION` | preregistro completado y GO independiente antes de ejecutar | `BLOCKED` |

Las nueve anomalías OHLC ya observadas en el holdout tienen tratamiento
`UNKNOWN/BLOCKED` en este preregistro. No se borran, corrigen, imputan ni
excluyen silenciosamente. Su tratamiento exige evidencia de fuente y una regla
explícita antes de cualquier evaluación.

La provenance de la fuente histórica candidata permanece `BLOCKED`: proveedor,
licencia/permitted-use, `acquired_at_utc`, documentación, lineage completo y
reproducción en worktree limpio deben verificarse. Los hashes aislados no
resuelven la procedencia legal.

## 9. Criterio de decisión futuro

El resultado económico solo podrá ser:

- `PASS_EDGE`: todos los gates duros pasan; IC unilateral inferior `>= +0,10R`;
  potencia suficiente; VALIDATION y HOLDOUT mantienen signo no negativo; y no
  hay concentración no declarada ni cambio de protocolo.
- `NO_EDGE`: todos los gates duros pasan, la potencia es suficiente y el IC
  superior queda `<= +0,10R`, o no supera `R0=0` bajo el contraste congelado.
- `REVIEW`: evidencia válida pero inconclusa, subpotenciada, inestable o con IC
  que cruza el MDE; nunca se eleva por opinión o ampliación post-hoc.
- `BLOCKED`: falta o falla cualquier gate duro de datos, fill, costes,
  horizonte, causalidad, provenance, reproducibilidad o autorización.

La precedencia es `BLOCKED > PASS_EDGE/NO_EDGE > REVIEW`. El estado actual de
este preregistro es `DRAFT_BLOCKED / NO EJECUTAR`; no se emite ningún veredicto
económico.

## 10. No-mezcla con IA

Este experimento no usa modelos, features, entrenamiento ni artefactos de IA.
`label_end_6` y `label_end_12` pertenecen a contratos de clasificación IA y no
son outcomes económicos. No se usarán para definir entry, exit, `net_R`, MDE,
baseline o veredicto.

La conciliación entre esos horizontes IA y este outcome económico es **NO
APLICABLE** a `EXP-PASS-EDGE-INTRADIA-01`; queda pendiente exclusivamente para
una futura IA mediante su propio contrato y preregistro.

## 11. Outputs mínimos antes de un veredicto

```text
reports/audits/experiments/pass_edge_intradia/EXP-PASS-EDGE-INTRADIA-01/
├── manifest.json
├── setups.jsonl
├── trades.jsonl
├── audit.json
└── report.md
```

`manifest.json` debe incluir dataset snapshot/hash, archivos y SHA-256, fuente,
licencia, adquisición UTC, configuración, costes, horizonte, sesiones,
regímenes, commits, generador, entorno, worktree y comandos. `audit.json` y
`report.md` deben mostrar gates, conteos por etapa, rechazos, `net_R`, baseline
nulo, IC, bootstrap, clustering, potencia, estabilidad y decisión.

## 12. Decisión de cierre del preregistro

No ejecutar. Antes de solicitar un GO independiente se debe completar el fill
económico M15, costes, horizonte, tratamiento de las nueve anomalías y
provenance/reproducibilidad. Ningún resultado de clasificación IA o diagnóstico
histórico puede sustituir esos requisitos ni producir `PASS_EDGE`.
