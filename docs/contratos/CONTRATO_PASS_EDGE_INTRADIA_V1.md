# Contrato CRO — PASS_EDGE intradía económico v1

> Enmienda vigente de Ruben (2026-09-11): se autoriza avanzar autonomamente con entrenamiento y evaluacion de IA sobre datos existentes e inmutables. No se requiere una nueva autorizacion humana para cada fase. La ausencia de licencia o permiso escrito de Dukascopy deja de ser un bloqueo interno y no se solicitara licencia. Rige `docs/contratos/ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md` sobre las restricciones anteriores de este documento. Los controles tecnicos se verifican durante el trabajo; sus fallos se reportan sin alterar datos ni fabricar certificaciones. Esta autorizacion no habilita trading ni promocion automatica a produccion.


**Estado:** NORMATIVO PARA DEFINIR EL GATE; NO EJECUTADO

**Owner:** D5 Assurance / CRO, con revisión D4 Datos y D6 Research

**Modo:** `LOCAL_ONLY`

**Alcance:** baseline económico intradía sin IA, sin entrenamiento, sin órdenes y sin promoción

## 1. Propósito y límites

Este contrato define cuándo una especificación económica intradía puede recibir
`PASS_EDGE`, `REVIEW`, `NO_EDGE` o `BLOCKED`. El gate mide expectativa económica
después de costes sobre una especificación congelada; no certifica un modelo de
IA, una predicción, una orden ni una autorización operativa.

El contrato no autoriza por sí mismo backtest, acceso a datos, modificación de
datasets, entrenamiento, Shadow Mode, MT5, broker, órdenes ni promoción. Toda
ejecución futura requiere un preregistro que complete los campos obligatorios de
este documento y la autorización del departamento correspondiente.

`PASS_EDGE` es un resultado científico condicionado, no un estado operativo.
`can_trade` permanece `false` salvo que exista un contrato de ejecución separado
y una decisión explícita de la autoridad del proyecto.

## 2. Unidad económica de análisis

La unidad primaria es un **setup económico canónico**, identificado por un
`setup_id` estable y observado en un único `decision_time`. El setup debe
contener, antes de observar su outcome:

- símbolo, venue, timeframe y dirección;
- `entry_time`/`entry_price`, regla de entrada y `decision_time`;
- `stop_price` estructural y riesgo inicial `R = abs(entry_price - stop_price)`;
- regla de salida, horizonte económico y `exit_time` máximo;
- `episode_id` o `chain_id` para dependencia y clustering;
- lineage completo hacia las barras y objetos visibles en `decision_time`.

Se acepta como máximo un outcome económico por `setup_id`. Duplicados,
reentradas del mismo episodio, barras repetidas o variantes de la misma
decisión no son observaciones independientes. Si no existe una identidad
estable o el riesgo inicial es cero/no finito, el gate es `BLOCKED`.

La población debe fijarse antes de inspeccionar resultados: filtros de símbolo,
sesión, régimen, dirección, elegibilidad, exclusiones y deduplicación forman
parte de la configuración congelada.

## 3. Outcome y baseline nulo

El outcome primario es `net_R`:

```text
gross_pnl_cash = signed_exit_move × position_units
cost_cash      = spread + commission + slippage + financing + otros costes preregistrados
net_R          = (gross_pnl_cash - cost_cash) / initial_risk_cash
```

Las unidades monetarias, conversión de moneda, redondeo, spread, comisión,
slippage, financiación y cualquier coste adicional deben estar congelados en el
preregistro. Los costes no pueden ajustarse después de ver resultados.

El **baseline nulo** es `R0 = 0 net_R por setup`: la expectativa económica no
debe ser positiva después de costes bajo la hipótesis nula. El contraste
confirmatorio primario es unilateral:

```text
H0: E[net_R] <= 0
H1: E[net_R] > 0
```

Win rate, profit factor, Sharpe, accuracy, log-loss, MFE, MAE y conteos de
clase son secundarios o descriptivos; ninguno sustituye a `net_R`.

## 4. Horizonte económico congelado

El horizonte económico no es una etiqueta IA. El preregistro debe declarar
exactamente uno de estos contratos de salida:

1. `FIXED_BARS`: timeframe, número de barras y precio de salida;
2. `SESSION_CLOSE`: sesión UTC, regla de cierre y precio de salida;
3. `FIRST_TOUCH_TIMEOUT`: reglas de TP/SL, prioridad si ambos tocan la misma
   barra y timeout máximo explícito.

La prioridad TP/SL intrabar, el tratamiento de gaps, cierres parciales,
comisiones y timeout deben ser deterministas. Cambiar el horizonte o la regla
de salida exige un nuevo preregistro. No se elige el horizonte que produzca el
mejor resultado.

`label_end_6` y `label_end_12` pertenecen a contratos de clasificación IA y no
son outcomes económicos de este baseline. No deben mezclarse con `net_R`, con
la definición de trade ni con el veredicto de este contrato. Su conciliación
queda **NO APLICABLE al baseline económico** y pendiente únicamente para una
futura IA mediante contrato/preregistro separado.

## 5. Particiones temporales y uso permitido

Salvo que un preregistro posterior justifique otras fechas antes de leer
resultados, se usarán estas particiones UTC, con límite final exclusivo:

| Partición | Ventana | Uso |
|---|---|---|
| `DESIGN` | `[2006-01-01, 2016-01-01)` | congelar especificación y revisar mecánica; no seleccionar con el resultado económico |
| `VALIDATION` | `[2016-01-01, 2021-01-01)` | comprobar estabilidad de la especificación congelada |
| `HOLDOUT` | `[2021-01-01, 2026-01-01)` | evaluación confirmatoria final, una sola lectura |

El HOLDOUT no puede seleccionar símbolos, filtros, sesiones, regímenes,
umbrales, horizonte, costes, TP, SL, entry ni reglas. Si el outcome cruza el
límite temporal de una partición, se excluye con razón registrada; no se
reubica en otra partición.

El preregistro debe declarar warmup, calendario, zona horaria, sesiones,
ventanas de indicadores y tratamiento de la primera/última observación. El
warmup no puede aportar outcomes ni información futura al setup.

## 6. MDE, potencia y tamaño muestral

El MDE económico primario es `+0,10R` de expectativa media neta por setup
independiente, con potencia objetivo `0,80` y `alpha=0,05` unilateral. El
preregistro debe calcular `n_required` sobre clusters independientes usando una
estimación de varianza y, cuando corresponda, intracluster correlation; `n>=30`
no sustituye el cálculo de potencia.

La evaluación debe conservar:

- número de setups y número de clusters por partición;
- varianza, ICC o método equivalente usado para `n_required`;
- supuestos, semilla y método del cálculo;
- potencia alcanzada o sensibilidad ante menor potencia.

Si falta el cálculo, el número de clusters es insuficiente o el HOLDOUT está
subpotenciado para el MDE congelado, el resultado no puede ser `PASS_EDGE`.
Será `REVIEW` si la evidencia mecánica es válida pero insuficiente; será
`BLOCKED` si además falta un requisito duro de datos, causalidad o
reproducibilidad.

## 7. Intervalos, clustering y contrastes

El intervalo primario será un IC unilateral del 95% para la media de `net_R`,
calculado con bootstrap por cluster. Cada réplica remuestrea clusters completos
(`episode_id` o `chain_id`), nunca filas individuales de un mismo episodio.
Semilla, número de réplicas (mínimo 10.000), estadístico, método para clusters
pequeños y tratamiento de `NaN` deben estar congelados.

Se reportará también IC bilateral del 95%, media, mediana, desviación, cuantiles,
número de clusters y distribución de `net_R`. La dependencia temporal no se
puede ocultar con un conteo de filas.

El contraste confirmatorio primario es uno solo: `E[net_R] > 0` con MDE
`+0,10R`. Las desagregaciones por periodo, sesión y régimen forman una familia
secundaria y deben usar Holm-Bonferroni (o Bonferroni) con alfa familiar `0,05`,
declarado antes de la ejecución. Toda lectura adicional es `EXPLORATORY` y no
puede elevar el estado.

## 8. Estabilidad obligatoria

El informe debe mostrar el mismo outcome económico por:

- partición temporal y año;
- sesión UTC preregistrada;
- régimen causal preregistrado, como tendencia/rango y terciles de volatilidad
  calculados solo con información disponible hasta `decision_time`.

Para `PASS_EDGE` se requiere:

1. IC primario unilateral inferior mayor o igual que `+0,10R`;
2. validación y HOLDOUT con signo no negativo y sin reversión material de signo;
3. ninguna celda secundaria obligatoria con evidencia corregida de expectativa
   neta negativa material;
4. número de clusters suficiente o estado explícito `NOT_TESTABLE` que impide
   `PASS_EDGE`;
5. ausencia de concentración no declarada en un único año, sesión o régimen.

Una estimación positiva pero por debajo del MDE, con IC que cruza cero/MDE,
inestabilidad temporal o subgrupos no testeables es `REVIEW`, no `PASS_EDGE`.

## 9. Causalidad y punto en el tiempo

Toda feature, filtro y nivel usado en `decision_time` debe ser observable con
timestamp menor o igual a ese instante. El outcome solo puede leer barras
posteriores a la decisión. Se exige:

- replay `FULL` frente a `PREFIX` para cada corte requerido;
- cero violaciones PIT y lineage resoluble;
- prioridad intrabar y disponibilidad de datos documentadas;
- no uso de etiquetas, resultados, PnL, máximos/mínimos futuros o estadísticas
  revisadas para construir la decisión;
- igualdad determinista con el mismo snapshot, configuración, código y entorno.

Cualquier look-ahead, selección post-resultado, leakage, outcome ambiguo o
lineage no resoluble produce `BLOCKED`, aunque `net_R` sea positivo.

## 10. Reproducibilidad y procedencia

El artefacto debe conservar, por cada entrada, transformación y salida:

- ruta, tamaño y SHA-256;
- `dataset_snapshot_id`, manifest y hash del manifest;
- proveedor, instrumento, venue, fuente, licencia y permitted-use;
- `acquired_at_utc`, parámetros de adquisición y documentación de fuente;
- timezone, sesiones, frontera de barra, OHLCV y semántica de volumen;
- regla de costes, configuración y hash canónico;
- script generador, commit de código, comando, Python/dependencias y semilla;
- rama/ref y estado del worktree;
- conteos antes/después, duplicados, huecos, anomalías, exclusiones y razones.

La reproducción confirmatoria exige `worktree_state=CLEAN`, commits resolubles,
hashes coincidentes, manifest completo y dos ejecuciones lógicamente idénticas.
Un reporte histórico o un hash aislado no certifica el estado actual.

## 11. Veto de provenance

La procedencia es un veto duro. Si cualquiera de proveedor, identidad del
instrumento, licencia/permitted-use, adquisición UTC, semántica temporal,
manifest, hash, generador, commit, worktree o lineage está ausente,
contradictorio o no verificable, el estado superior es `BLOCKED`.

No se permite sustituir spot por futuros CME `6E`, imputar volumen/open
interest, reparar o eliminar OHLC silenciosamente, ni convertir una anomalía de
fuente en PASS mediante un proxy. La evidencia legal no se infiere de hashes.

## 12. Estados y precedencia

Se aplica esta precedencia: `BLOCKED` > `PASS_EDGE`/`NO_EDGE` > `REVIEW`.

### `PASS_EDGE`

Solo cuando todos los gates duros de causalidad, datos, provenance,
reproducibilidad y costes son `PASS`; el tamaño muestral alcanza la potencia
preregistrada; el IC primario inferior es `>= +0,10R`; la estabilidad requerida
es satisfecha; y no hubo cambios post-resultado. No implica trading.

### `NO_EDGE`

Solo cuando todos los gates duros son `PASS`, la potencia es suficiente y el IC
superior del efecto económico queda `<= +0,10R`, o la estimación confirmatoria
no supera `R0=0` bajo el contraste preregistrado. Es un cierre científico
negativo, no una invitación a optimizar sobre el mismo HOLDOUT.

### `REVIEW`

La mecánica y la provenance son utilizables, pero la evidencia es inconclusa:
MDE no alcanzado, IC que cruza el umbral, potencia insuficiente sin fallo duro,
inestabilidad o celda secundaria no testeable. `REVIEW` nunca se transforma en
`PASS_EDGE` por opinión ni por ampliar post-hoc el universo.

### `BLOCKED`

Falta o falla un gate duro: datos/provenance, PIT, lineage, identidad de unidad,
costes, horizonte, manifest, hash, generador, commit, worktree limpio,
determinismo o autorización contractual. Debe conservarse la razón exacta y no
se puede compensar con una métrica positiva.

## 13. Aplicación al estado actual

Este contrato no cambia ni certifica los artefactos existentes. La comparación
intradía actual usa clasificación IA, `accuracy/log-loss` y
`label_end_12`; no es una evaluación económica `net_R` bajo este contrato.
Además, la auditoría de datos vigente mantiene provenance `BLOCKED` y el
checkout actual está sucio. Por tanto, ningún resultado actual puede declararse
`PASS_EDGE` con este documento.

## 14. Artefactos mínimos de una futura evaluación

```text
docs/experimentos/EXP_PASS_EDGE_INTRADIA_<ID>_PREREGISTRATION.md
reports/audits/experiments/pass_edge_intradia/<ID>/manifest.json
reports/audits/experiments/pass_edge_intradia/<ID>/trades.jsonl
reports/audits/experiments/pass_edge_intradia/<ID>/audit.json
reports/audits/experiments/pass_edge_intradia/<ID>/report.md
```

El informe final debe devolver `AGENTE`, `DEPARTAMENTO`, `TAREA`, `STATUS`,
`EVIDENCIA`, `ARCHIVOS`, `RIESGOS` y `SIGUIENTE ACCIÓN`, incluyendo el estado
por gate y el veredicto económico sin mezclarlo con IA ni con autoridad de
órdenes.
