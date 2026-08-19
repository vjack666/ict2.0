# AUDITORÍA TEMPORAL AHF / MTF — Duración, transiciones y retrocesos

**Estado:** NORMATIVO — diseño de auditoría; no es backtest ni auditoría de PnL  
**Objetivo:** medir si el AHF se comporta como un analista humano que recorre temporalidades, espera condiciones, baja de TF, vuelve atrás cuando una condición se invalida y reanuda desde la capa correcta.

## 1. Qué audita

Esta auditoría no pregunta si una señal gana dinero. Pregunta **cómo navega el motor en el tiempo**:

```text
¿cuántas velas espera?
¿cuánto permanece en cada estado?
¿cuándo baja de TF?
¿cuándo sube de vuelta?
¿cuántas velas retrocede?
¿cuántas veces reabre una capa?
¿cuánto tarda en completar una cadena?
¿cuándo se queda atascado?
```

El marco conceptual es el de un proceso de estados con **holding/sojourn times** y transiciones. Para esta auditoría nos interesa especialmente la duración condicionada a la transición y no sólo el estado final; por eso la lectura es más cercana a un análisis semi-Markov que a un loop fijo. La literatura financiera muestra que las duraciones de estados pueden contener información adicional y que la hipótesis de duración sin memoria puede ser demasiado restrictiva. cite-local-placeholder

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

La auditoría trabaja sobre esos traces, nunca reconstruye retrospectivamente un estado utilizando información posterior.

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

Reportar:

- mínimo;
- mediana;
- media;
- p75;
- p90;
- p95;
- máximo.

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

También medir:

`rollback_bars = rollback_bar - invalidation_origin_bar`

y:

`recovery_bars = next_reconfirmation_bar - rollback_bar`

### 4.6 Reentradas

Contar:

- reentry_count por TF;
- invalidation_count por TF;
- revisits al mismo estado;
- revisits al mismo contexto congelado;
- ciclos completos `WAIT → LOCKED → INVALIDATED → WAIT`.

## 5. Métricas de comportamiento tipo trader

### A. Persistencia

¿Cuánto tiempo permanece el agente investigando una capa antes de abandonarla?

### B. Capacidad de corrección

Después de una invalidación, ¿regresa exactamente a la capa responsable o reinicia todo el análisis?

### C. Eficiencia de navegación

`navigation_efficiency = confirmed_progress / total_transitions`

No es una métrica de rentabilidad; mide cuánto movimiento del grafo fue necesario para producir progreso de estado.

### D. Backtracking excesivo

Identificar trayectorias con muchos retrocesos:

```text
D1 → H4 → H1 → H4 → H1 → H4 ...
```

Esto puede indicar un contrato demasiado inestable o una condición mal definida.

### E. Stuck states

Detectar estados donde:

`T_hold > p95 histórico`

sin confirmación ni invalidación.

### F. Zonas de indecisión

Contar alternancias rápidas:

```text
LOCKED → WAIT → LOCKED → WAIT
```

dentro de una ventana corta.

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

También:

`TF_dwell_share = dwell_time_at_tf / total_trace_time`

Esto permite responder si el AHF realmente “pasea” entre escalas o simplemente cae una vez a LTF y ya no vuelve.

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

Separar estrictamente:

- existencia de cadena;
- duración de cadena;
- profundidad alcanzada;
- completitud;
- outcome.

No convertir estos números en edge de trading.

## 8. Auditoría de causalidad temporal

Cada transición debe satisfacer:

`transition_time >= all evidence times used for the transition`

y para snapshots MTF:

`as_of(tf, t) = max{i | time[i] <= t}`

Además:

- ninguna capa inferior puede usar una confirmación HTF posterior;
- una invalidación sólo existe desde el momento en que fue observable;
- un rollback no puede aparecer en el trace antes de su evento causal;
- un contexto LOCKED no puede cambiar silenciosamente: debe existir un evento de actualización o invalidación.

## 9. Auditoría de capacidad de corrección

Ésta es la parte central de la petición del usuario.

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

El resultado debe permitir distinguir:

```text
CORRECCIÓN LOCAL
H1 → WAIT_H1
```

frente a:

```text
CORRECCIÓN PROFUNDA
H1 → H4 → WAIT_H4
```

frente a:

```text
RESET TOTAL
LTF → WAIT_D1
```

Los tres comportamientos deben ser cuantificados por separado.

## 10. Métricas mínimas de salida

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
```

## 11. Gates propuestos

### TNA-01 — Integridad del trace
PASS si todos los estados tienen enter/exit coherentes y no existen timestamps imposibles.

### TNA-02 — PIT
PASS si no existen transiciones, invalidaciones o snapshots que dependan del futuro.

### TNA-03 — Rollback determinista
PASS si una invalidación conduce al estado definido por contrato y conserva historial.

### TNA-04 — Revisitabilidad
PASS si el AHF puede reabrir una capa sin borrar el contexto histórico previo.

### TNA-05 — Duración observable
PASS si todas las transiciones reportan barras y timestamps comparables.

### TNA-06 — No-stuck / clasificación
No exige cero estados atascados. Exige que estén identificados y cuantificados para poder decidir si son comportamiento esperado o defecto.

## 12. Qué NO mide

Esta auditoría **NO** demuestra:

- win rate;
- expectancy;
- profit factor;
- Sharpe;
- edge de trading;
- rentabilidad de la navegación.

Su función es comprobar que, antes del backtest, el motor sabe **navegar, esperar, corregirse y volver atrás** de forma temporalmente auditable.

## 13. Artefactos

```text
reports/audits/ahf_temporal_navigation.json
docs/AUDITORIA_TEMPORAL_AHF_MTF.md
```

## 14. Gate antes de backtest

El backtest multi-TF queda bloqueado si:

- hay violaciones PIT;
- hay rollback sin evento causal;
- existen reescrituras de contexto LOCKED;
- no se puede reconstruir el trace completo;
- las duraciones no pueden medirse de forma reproducible.

## 15. Siguiente ejecución

1. Instrumentar el AHF para emitir traces persistentes.
2. Ejecutar esta auditoría sobre el universo 20Y y por TF/cadena.
3. Analizar distribución de duración y rollback.
4. Clasificar stuck/revisit patterns.
5. Corregir el AHF si la navegación real no coincide con el contrato.
6. Repetir hasta Gate TNA PASS.
7. Sólo después ejecutar el experimento `SEQUENCE depth × Context State` con stop fijo.
