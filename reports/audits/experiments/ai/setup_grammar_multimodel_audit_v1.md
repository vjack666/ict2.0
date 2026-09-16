# Auditoria Semantica Multimodelo v1

## Dictamen

Estado: **MORE_DETERMINISTIC_WORK_REQUIRED**. La clasificacion es paralela y diagnostica; no altera `grammar_labels`, no crea candidatos operables y mantiene `can_trade=false`.

## Cobertura

- Filas auditadas: `286`.
- ABSTAIN: `120`; REJECT: `166`.

## Coincidencias estructurales

| Familia | ABSTAIN | REJECT | Total | Estado |
| --- | ---: | ---: | ---: | --- |
| PO3 | 22 | 5 | 27 | PENDING_EXECUTION_GEOMETRY |
| TURTLE_SOUP | 0 | 2 | 2 | PENDING_EXECUTION_GEOMETRY |
| SILVER_BULLET | 0 | 1 | 1 | NO_CERTIFIED_COUNT |

## Limites

- La evidencia M15 se corta en `time <= decision_time`; no se consulta futuro.
- La ventana de sweep usa la definicion canonica local con lookback 20 y exige que el ultimo sweep este a no mas de 20 velas de la decision.
- Ninguna coincidencia pasa a `PASS`: faltan RR, coste, fill y ancla materializada de `sweep_ts`.
- Silver Bullet no recibe conteo certificado hasta reconciliar las horas exactas que difieren entre los documentos locales.
