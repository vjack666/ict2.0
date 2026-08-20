# AUDITORÍA TEMPORAL AHF / MTF — Duración, transiciones, retrocesos y magnitud de eventos

**Estado:** NORMATIVO — diseño de auditoría; no es backtest ni auditoría de PnL
**Objetivo:** medir si el AHF se comporta como un analista humano que recorre temporalidades, espera condiciones, baja de TF, vuelve atrás cuando una condición se invalida y reanuda desde la capa correcta.

## 1. Qué audita

Esta auditoría no pregunta si una señal gana dinero. Pregunta **cómo navega el motor en el tiempo** y qué magnitud de movimiento existe alrededor de FVG/OB:

```text
¿cuántas velas espera?
¿cuánto permanece en cada estado?
¿cuándo baja de TF?
¿cuándo sube de vuelta?
¿cuántas velas retrocede?
¿cuántas veces reabre una capa?
¿cuánto tarda en completar una cadena?
¿cuándo se queda atascado?
¿qué tamaño tiene el FVG/OB en pips?
¿cuántos pips recorre a favor después de FVG/OB?
¿cuántos pips recorre en contra después de FVG/OB?
```

El marco conceptual es el de un proceso de estados con **holding/sojourn times** y transiciones. Para esta auditoría nos interesa especialmente la duración condicionada a la transición y no sólo el estado final; la lectura es más cercana a un análisis semi-Markov que a un loop fijo.

## 2. Unidad de observación

Cada ejecución del AHF debe producir un **trace temporal inmutable**:

```text
state_enter
state_exit
active_tf
transition_event
transition_bar
transition_time
parent_state
invalidation_reason
context_snapshot_id
```

Además, los eventos FVG/OB observados durante el trace pueden adjuntarse como objetos descriptivos:

```text
object_id
object_type = FVG | OB
symbol
TF
birth_bar
birth_time
direction
zone_low
zone_high
```

La auditoría trabaja sobre esos traces y objetos con su `as_of(t)` correspondiente; nunca reconstruye retrospectivamente un estado utilizando información posterior.

## 3. Estados auditados

```text
WAIT_D1
D1_LOCKED
WAIT_H4
H4_LOCKED
WAIT_H1
WAIT_LTF
SETUP_READY
OUTCOME
```

También se registran retornos:

```text
H1_INVALIDATED → WAIT_H1
H4_INVALIDATED → WAIT_H4
D1_INVALIDATED → WAIT_D1
```

La implementación debe conservar toda la trayectoria; no se permite comprimir los retrocesos en un único estado final.

## 4. Métricas de tiempo

### 4.1 Latencia hasta encontrar condición

Para cada capa:

`T_find = first_confirmed_bar - state_enter_bar`

Reportar mínimo, mediana, media, p75, p90, p95 y máximo.

### 4.2 Duración de estado

`T_hold = state_exit_bar - state_enter_bar`

También en tiempo de reloj:

`duration_time = state_exit_time - state_enter_time`

No mezclar barras H1 con barras H4 como si fueran la misma unidad. Toda métrica debe conservar `tf` y además una duración temporal absoluta.

### 4.3 Tiempo de descenso

Medir desde la confirmación de una capa hasta la primera consulta válida de la siguiente:

`T_down = child_first_active_bar - parent_confirmation_bar`

### 4.4 Tiempo hasta SETUP_READY

`T_setup = setup_ready_bar - first_active_bar`

Reportar por camino:

```text
D1→H4→H1→LTF
D1→H4→H1
D1→H4
```

### 4.5 Retroceso / rollback

Para cada invalidación:

`rollback_depth = previous_active_level - new_active_level`

Ejemplo:

```text
D1(0) → H4(1) → H1(2) → invalidación H4
rollback_depth = 1
```

También medir `rollback_bars` y `recovery_bars`.

### 4.6 Reentradas

Contar reentry_count por TF, invalidation_count por TF, revisits al mismo estado, revisits al mismo contexto congelado y ciclos completos `WAIT → LOCKED → INVALIDATED → WAIT`.

## 5. Métricas de comportamiento tipo trader

### A. Persistencia

¿Cuánto tiempo permanece el agente investigando una capa antes de abandonarla?

### B. Capacidad de corrección

Después de una invalidación, ¿regresa exactamente a la capa responsable o reinicia todo el análisis?

### C. Eficiencia de navegación

`navigation_efficiency = confirmed_progress / total_transitions`

No es una métrica de rentabilidad; mide cuánto movimiento del grafo fue necesario para producir progreso de estado.

### D. Backtracking excesivo

Identificar trayectorias con muchos retrocesos, por ejemplo `D1 → H4 → H1 → H4 → H1 ...`.

### E. Stuck states

Detectar estados donde `T_hold > p95 histórico` sin confirmación ni invalidación.

### F. Zonas de indecisión

Contar alternancias rápidas `LOCKED → WAIT → LOCKED → WAIT` dentro de una ventana corta.

## 6. Métricas de navegación multi-TF

Para cada trace:

```text
TF visits
TF switches
upward switches
downward switches
same-TF revisits
max depth reached
min depth after rollback
```

También `TF_dwell_share = dwell_time_at_tf / total_trace_time`.

## 7. Métricas de cadena

Para cada secuencia:

```text
sequence_start
sequence_end
sequence_duration
bars_between_events
bars_between_depth_changes
bars_from_depth_k_to_depth_k+1
rollback_count
reopen_count
complete = true|false
```

Separar estrictamente existencia de cadena, duración de cadena, profundidad alcanzada, completitud y outcome.

## 8. Magnitud FVG / OB y recorrido posterior (DESCRIPTIVO, NO TP)

Esta sección responde a una necesidad específica de auditoría: medir **qué tamaño tenía el objeto** y **qué distancia recorrió el precio después de que el objeto apareció**, sin convertir ninguna distancia en target, stop o regla de entrada.

### 8.1 Tamaño del FVG en pips

Para un objeto FVG con límites `[zone_low, zone_high]`:

`fvg_size_pips = abs(zone_high - zone_low) / pip_size(TF, symbol)`

### 8.2 Tamaño del OB en pips

Para un OB con límites `[zone_low, zone_high]`:

`ob_size_pips = abs(zone_high - zone_low) / pip_size(TF, symbol)`

Para EURUSD se usará por defecto `pip_size = 0.0001`, salvo que la metadata del símbolo indique otra convención.

### 8.3 Movimiento posterior a favor y en contra

Desde la barra de nacimiento/confirmación del objeto `b0`, medir en una ventana descriptiva `H`:

- `max_favorable_pips`: máxima excursión posterior en la dirección del objeto.
- `max_adverse_pips`: máxima excursión posterior en contra de la dirección del objeto.
- `end_move_pips`: desplazamiento firmado al cierre de la barra final de la ventana.
- `bars_to_max_favorable`.
- `bars_to_max_adverse`.

Para un objeto bullish:

```text
favorable = future_high - reference_price
adverse   = reference_price - future_low
```

Para un objeto bearish se invierten las direcciones.

### 8.4 Ventanas de observación

Reportar al menos:

```text
+1 barra
+3 barras
+6 barras
+12 barras
+24 barras
+48 barras
```

La auditoría debe poder comparar el mismo objeto en varias ventanas sin llamar a ninguna de ellas `TP`.

### 8.5 Precio de referencia

El JSON debe guardar explícitamente `reference_price` y `reference_rule`.

Regla por defecto:

```text
FVG → close de la barra de confirmación del FVG
OB  → close de la barra de nacimiento/confirmación del OB
```

No se permite cambiar la regla de referencia después de observar resultados.

### 8.6 Métricas agregadas

Por `TF × object_type × direction` reportar:

```text
object_count
size_pips_stats
favorable_pips_stats
adverse_pips_stats
end_move_pips_stats
bars_to_favorable_stats
bars_to_adverse_stats
favorable/adverse ratio descriptivo
```

### 8.7 Lo que NO significa

Estas métricas **no son**:

- Take Profit;
- Stop Loss;
- entrada;
- expectancy;
- R de sistema;
- edge de trading.

Su propósito es caracterizar la **geometría y dinámica posterior del objeto**. Podrán utilizarse después como evidencia para diseñar hipótesis, pero no para declarar una estrategia.

## 9. Auditoría de causalidad temporal

Cada transición debe satisfacer:

`transition_time >= all evidence times used for the transition`

y para snapshots MTF:

`as_of(tf, t) = max{i | time[i] <= t}`

Además:

- ninguna capa inferior puede usar una confirmación HTF posterior;
- una invalidación sólo existe desde el momento en que fue observable;
- un rollback no puede aparecer en el trace antes de su evento causal;
- un contexto LOCKED no puede cambiar silenciosamente: debe existir un evento de actualización o invalidación;
- las métricas FVG/OB posteriores sólo usan barras `> birth_bar`; nunca se permite usar barras anteriores para medir movimiento posterior.

## 10. Auditoría de capacidad de corrección

Para cada fallo de condición:

```text
CONDICIÓN FALLA
      ↓
¿qué capa causó el fallo?
      ↓
¿cuántas velas retrocede AHF?
      ↓
¿a qué estado regresa?
      ↓
¿cuánto tarda en volver a confirmar?
      ↓
¿reutiliza contexto válido o lo recalcula?
```

Distinguir:

```text
CORRECCIÓN LOCAL
H1 → WAIT_H1
```

```text
CORRECCIÓN PROFUNDA
H1 → H4 → WAIT_H4
```

```text
RESET TOTAL
LTF → WAIT_D1
```

Los tres comportamientos deben ser cuantificados por separado.

## 11. Métricas mínimas de salida

El JSON de auditoría debe contener como mínimo:

```text
trace_count
eligible_traces
completed_traces
mean_trace_bars
median_trace_bars
p90_trace_bars
state_durations_by_state
transition_counts
transition_latency_by_edge
rollback_count
rollback_depth_distribution
rollback_bars_distribution
reconfirmation_bars_distribution
revisit_count_by_tf
max_depth_distribution
stuck_state_count
stuck_state_rate
causal_violations
asof_violations
context_rewrite_violations
fvg_size_pips_by_tf
ob_size_pips_by_tf
fvg_favorable_pips_by_tf
fvg_adverse_pips_by_tf
ob_favorable_pips_by_tf
ob_adverse_pips_by_tf
object_move_windows
```

## 12. Gates propuestos

### TNA-01 — Integridad del trace
PASS si todos los estados tienen enter/exit coherentes y no existen timestamps imposibles.

### TNA-02 — PIT
PASS si no existen transiciones, invalidaciones, snapshots u objetos que dependan del futuro.

### TNA-03 — Rollback determinista
PASS si una invalidación conduce al estado definido por contrato y conserva historial.

### TNA-04 — Revisitabilidad
PASS si el AHF puede reabrir una capa sin borrar el contexto histórico previo.

### TNA-05 — Duración observable
PASS si todas las transiciones reportan barras y timestamps comparables.

### TNA-06 — No-stuck / clasificación
No exige cero estados atascados. Exige que estén identificados y cuantificados.

### TNA-07 — Magnitud de objetos
PASS si FVG/OB tienen tamaño en pips reproducible y las ventanas posteriores están estrictamente después del `birth_bar`.

### TNA-08 — Separación de medición y trading
PASS si ninguna métrica de distancia posterior es interpretada por el auditor como TP/SL/entrada.

## 13. Qué NO mide

Esta auditoría **NO** demuestra:

- win rate;
- expectancy;
- profit factor;
- Sharpe;
- edge de trading;
- rentabilidad de la navegación;
- que una distancia recorrida sea un TP.

Su función es comprobar que, antes del backtest, el motor sabe **navegar, esperar, corregirse y volver atrás** y, además, permite caracterizar la geometría posterior de FVG/OB de forma reproducible.

## 14. Artefactos

```text
reports/audits/ahf_temporal_navigation.json
AUDITORIA_TEMPORAL_AHF_MTF.md
```

## 15. Gate antes de backtest

El backtest multi-TF queda bloqueado si:

- hay violaciones PIT;
- hay rollback sin evento causal;
- existen reescrituras de contexto LOCKED;
- no se puede reconstruir el trace completo;
- las duraciones no pueden medirse de forma reproducible;
- la medición de magnitud usa barras anteriores al nacimiento del objeto;
- la implementación convierte estas métricas descriptivas en reglas de TP/SL sin un EXP separado.

## 16. Siguiente ejecución

Cuando Hermes reciba exactamente:

> **`ejecuta auditoria temporal`**

debe:

1. verificar dataset EURUSD 20Y + SHA256/metadata;
2. instrumentar/consumir traces AHF reales;
3. ejecutar TNA-01..TNA-08;
4. calcular duración, latencia, rollback, revisitas y estados atascados;
5. calcular tamaño FVG/OB en pips;
6. calcular recorrido posterior favorable/adverso y `end_move_pips` en ventanas descriptivas;
7. generar JSON + Markdown;
8. guardar los artefactos bajo `audits/` / `reports/audits/`;
9. actualizar `.hermes-index.md` y worklog;
10. si algún gate falla, corregir, probar y volver a auditar hasta obtener un resultado aceptable.

Sólo después de un Gate TNA aceptable se habilita el experimento `SEQUENCE depth × Context State` con stop fijo.
