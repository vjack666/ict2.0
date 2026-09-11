# SDD — Productor de señal mecánica v1

**Estado:** Fase 1 `IMPLEMENTED_DIAGNOSTIC_ONLY`; Fase 2 `DRAFT_BLOCKED`.
**Autoridad:** cliente; D2 implementa, D5 audita.
**Ámbito:** respuesta explicable del productor y futuro contrato de señal para
`mechanical_bot/`. No modifica la autoridad de `engine/`.

## 1. Propósito y frontera

El productor responde de forma completa al consumidor mecánico sin convertir el
snapshot canónico de lectura en una orden. La salida de Fase 1 es
`signal_assessment`, una evaluación explicable con `NO_SIGNAL` o
`CANDIDATE_SIGNAL`.

`NO_SIGNAL` no es un error ni una recomendación. Declara que no existe un
contrato mecánico válido y conserva `entry_authorized=false`.

## 2. Contrato Fase 1 — respuesta explicable

| Campo | Regla |
| --- | --- |
| `status` | `NO_SIGNAL` o `CANDIDATE_SIGNAL` |
| `code` | causa estable y legible por máquina |
| `detail` | explicación para el operador |
| `required_fields` | `symbol`, `direction`, `probability`, `confirmed`, `asof_time` |
| `observed_fields` | campos publicados, sin inferir valores faltantes |
| `missing_fields` | presente si el payload es inválido |
| `next_condition` | siguiente requisito real, no una predicción |
| `entry_authorized` | siempre `false` |
| `evaluated_at` | UTC de la evaluación |

Estados:

- `MECHANICAL_PRODUCER_UNAVAILABLE`: no existe snapshot mecánico.
- `MECHANICAL_SNAPSHOT_UNREADABLE`: existe, pero no puede leerse.
- `MECHANICAL_SNAPSHOT_INVALID`: falta o invalida el contrato.
- `MECHANICAL_SNAPSHOT_AVAILABLE`: candidato presente; readiness mantiene el
  veto de entrada.

El campo histórico `snapshot` puede permanecer `null` cuando no hay señal. La
respuesta autoridad para el operador es `signal_assessment`; ningún valor se
rellena con `direction_hint`, contexto, IA diagnóstica o una probabilidad
sintética.

## 3. Contrato Fase 2 — productor automático pendiente

La futura salida operable deberá ser atómica y contener:

```json
{
  "symbol": "EURUSD",
  "direction": "BUY | SELL",
  "probability": 0.0,
  "confirmed": true,
  "asof_time": "ISO-8601 UTC"
}
```

No se implementa ni publica hasta congelar y verificar:

1. reglas deterministas de dirección, con entradas de vela cerrada y prioridad
   entre D1/H4/H1/M15;
2. definición causal de `confirmed`, distinta del estocástico final del bot;
3. método calibrado de probabilidad con train/validation/OOS, Brier y curva de
   calibración; `score_to_probability()` no es sustituto;
4. contrato de datos, decisión temporal y rechazo de feed inválido;
5. FULL/PREFIX, determinismo, fixtures adversariales y bitácora hash;
6. gate de edge y autorización independiente antes de cualquier promoción.

La IA actual permanece en Shadow Mode y no puede producir esta salida. Context
State, Wyckoff y `direction_hint` permanecen evidencia diagnóstica.

## 4. Invariantes

- `engine.can_trade=false` y `entry_authorized=false` no cambian.
- `mechanical_bot` vuelve a validar sus seis gates antes de `order_send`.
- Fase 1 no crea `latest_snapshot.json`, ciclo, acción MT5 ni orden.
- Fase 2 requiere una misión nueva, preregistro y auditoría D5.
