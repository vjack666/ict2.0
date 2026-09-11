# SDD — Productor de señal mecánica v1

**Estado:** Fase 1 `IMPLEMENTED_DIAGNOSTIC_ONLY`; Fase 2A
`IMPLEMENTED_DIAGNOSTIC_ONLY`; Fase 2B `DRAFT_BLOCKED`.
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

## 3. Contrato Fase 2A — cadena determinista diagnóstica

El ensamblador canónico publica `mechanical_signal_assessment` y el terminal lo
proyecta al operador. Nunca escribe `latest_snapshot.json`. La respuesta tiene
solo tres estados: `BLOCKED`, `NO_SIGNAL` y `CANDIDATE_SETUP`; este último no
incluye `BUY`, `SELL`, `probability` ni `confirmed`.

La cadena congelada y su mínima evidencia causal, siempre con `time <=
decision_time`, es:

| Paso | Evidencia mínima cerrada | Rechazo estable |
| --- | --- | --- |
| contexto | H4 y H1 con `structure_bias` coherente con la dirección contextual y lado permitido | `HTF_CONFLICT` |
| sweep M15 | `m15_evidence.sweep=true`, producido causalmente y con fuente identificada | `NO_SWEEP` o `SWEEP_EVIDENCE_UNAVAILABLE` |
| displacement M15 | `m15_evidence.displacement=true` posterior al sweep | `NO_DISPLACEMENT` |
| BOS/CHOCH M15 | `m15_evidence.bos_or_choch=true` compatible y posterior | `NO_BOS` |
| FVG/OB M15 | `m15_evidence.fvg_or_ob=true` desde objeto canónico | `NO_FVG_OR_OB` |
| retest M15 | `m15_evidence.retest=true` con toque cerrado posterior | `WAIT_RETEST` |

La ausencia de velas M15 es `M15_DATA_UNAVAILABLE`; un snapshot no canónico,
incompleto o que rompa la frontera observacional es `BLOCKED`. El sistema no
deduce un sweep de una zona, `direction_hint`, Wyckoff, IA, BOS aislado ni
marcadores legacy. Hasta que el motor publique la evidencia de sweep, la
abstención explícita es el resultado correcto.

`context_direction` es contexto explicativo, no una dirección operable. M5/M1
permanece en `micro_confirmation` como diagnóstico separado y el estocástico
M15 sigue siendo un gate final exclusivo del bot.

Cada actualización de motor registra `SIGNAL_ASSESSMENT` en la caja negra con
la evaluación, hash SHA-256 del snapshot canónico, fuente y `decision_time`.
Las pruebas sintéticas cubren cada rechazo, candidato y la igualdad
FULL/PREFIX; el ensamblador recorta las velas al `decision_time` antes de
evaluar.

## 4. Contrato Fase 2B — productor automático pendiente

El gate implementado `engine.mechanical_signal_publication` acepta un
certificado independiente solo si todos estos campos tienen estado `PASS`:
`direction_rule`, `confirmation`, `calibration`, `abstention_ood`,
`costs_fill`, `causality`, `provenance`, `edge` y
`production_authorization`.

La regla direccional congelada para una futura publicación es única:
`CANDIDATE_CONTEXT_DIRECTION_V1`. Un `CANDIDATE_SETUP` con
`context_direction=BULLISH` mapea a `BUY`; con `BEARISH` mapea a `SELL`. Es
aceptable únicamente si el certificado declara esa misma regla. `confirmed`
significa `PHASE2A_CHAIN_COMPLETE_CLOSED_M15_V1`: cadena cerrada completa al
`decision_time`; no incorpora el cruce estocástico, que sigue siendo un gate
posterior del bot.

El certificado de calibración debe aportar una probabilidad finita entre 0 y
1, `fit_partition=VALIDATION_ONLY`,
`oos_partition=HOLDOUT_NEVER_USED_FOR_FIT`, Brier y hash de la curva de
fiabilidad. El gate no calcula ni acepta `score_to_probability()` como
evidencia. Cuando cualquiera de estos requisitos falla, devuelve `BLOCKED` y
no genera el contrato JSON ni escribe `latest_snapshot.json`.

La implementación no está conectada al publicador porque el estado actual del
preregistro económico es `DRAFT_BLOCKED / NO EJECUTAR`: provenance,
reproducibilidad, costes/fill, horizonte, potencia/estabilidad y autorización
no tienen `PASS`. Esta frontera evita confundir infraestructura de validación
con una certificación científica.

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

## 5. Invariantes

- `engine.can_trade=false` y `entry_authorized=false` no cambian.
- `mechanical_bot` vuelve a validar sus seis gates antes de `order_send`.
- Fase 1 no crea `latest_snapshot.json`, ciclo, acción MT5 ni orden.
- Fase 2B requiere preregistro, auditoría D5 y todos los gates de datos,
  calibración y edge antes de cualquier publicación atómica.
