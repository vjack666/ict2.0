# SDD — Arbitraje de reglas ICT/Wyckoff y ejecución manual V1

**Fecha:** 2026-09-10  
**Estado:** COMPLETO PARA REVISIÓN · no autoriza trading automático  
**Propietario:** D2 Ingeniería · revisión D5 Assurance

## 1. Objetivo

Separar contexto, conflicto, gatillo y autoridad para que una contradicción entre D1/H4/M15/Wyckoff sea legible y no produzca una dirección implícita.

## 2. No objetivos

No cambia la estrategia ICT, no entrena IA, no modifica datasets, no convierte Wyckoff en autoridad de entrada y no cambia `can_trade=false` del snapshot canónico.

## 3. Modelo de estados

`ALIGNED`: contexto y dirección comparables coinciden.  
`AGAINST`: la secuencia observada va contra el contexto.  
`MIXED`: las temporalidades no coinciden.  
`UNRESOLVED`: falta evidencia o dirección comparable.  
`COUNTERTREND`: `AGAINST` más evento Wyckoff de transición y confirmación M15; es una etiqueta, no una orden.

## 4. Autoridades

| Campo | Significado | Puede autorizar entrada |
|---|---|---|
| `direction_hint` | contexto D1/H4 | no |
| `structure_bias` | lectura por TF | no |
| `wyckoff.phase_state` | relación Wyckoff/ICT | no |
| `stochastic_m15` | gatillo cerrado | solo junto al contrato de entrada |
| `manual_direction` | elección humana | sí, en modo manual explícito |

## 5. Contrato de entrada manual

1. MT5 conectado y `execution_enabled=true`.
2. Bot activado manualmente.
3. Operador selecciona un único lado.
4. En Londres, el lado permitido es SELL según la configuración solicitada.
5. El servicio espera el cruce estocástico M15 correspondiente; no abre al seleccionar el lado.
6. Se abre un solo ciclo con el lote inicial.
7. El ciclo se vigila y se cierra por TP flotante agregado o pérdida máxima; las recompras no crean dirección.

## 6. Contrato de salida y recuperación

El ciclo no se duplica. Una respuesta incierta del broker conserva el ciclo y pasa a `ERROR`; la reconciliación de posiciones es obligatoria antes de reintentar.

## 7. Verificación requerida

Tests unitarios de arbitraje, tests de snapshot sin mutación, tests de selección manual sin envío inmediato, test de Londres BUY bloqueado y SELL pendiente, y evidencia de caja negra para cada transición.

## 8. Riesgos

Los conflictos pueden ser correctos. El principal riesgo es que el usuario interprete contexto como señal. El visor debe mostrar siempre `contexto`, `gatillo`, `autoridad` y `estado de ejecución` en campos separados.

## 9. Criterio de completitud

Este SDD está completo cuando todos los campos de autoridad tienen productor, consumidor, regla de precedencia, estado de ausencia y test asociado. La implementación queda sujeta a esa matriz y a revisión independiente.
