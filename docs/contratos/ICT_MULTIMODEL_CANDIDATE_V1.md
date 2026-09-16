# ICT_MULTIMODEL_CANDIDATE_V1

**Estado:** `DRAFT_FOR_IMPLEMENTATION`
**Ambito:** contrato comun de candidato determinista, no contrato de trading.

## Familias y contratos fuente

- `PO3`: `docs/ict/08_POWER_OF_THREE.md`.
- `TURTLE_SOUP`: `docs/ict/06_TURTLE_SOUP.md`.
- `SILVER_BULLET`: `docs/ict/07_SILVER_BULLET.md`, solo tras el gate temporal
  de `docs/ict/01_KILLZONES.md`.

El contrato comun no suaviza condiciones particulares. En particular, PO3
requiere alineacion HTF, Turtle Soup permite el giro contratrend con su MSS,
y Silver Bullet requiere killzone valida, sweep y desplazamiento/FVG.

## Esquema minimo

```json
{
  "candidate_id": "sha256-stable-id",
  "strategy_family": ["PO3"],
  "decision_time": "UTC ISO-8601",
  "symbol": "EURUSD",
  "direction": 1,
  "split": "TRAIN",
  "htf_context": {},
  "session": {},
  "killzone": {},
  "sweep_evidence": {},
  "structure_evidence": {},
  "displacement_evidence": {},
  "fvg_evidence": {},
  "ob_evidence": {},
  "pd_array_evidence": {},
  "execution_evidence": {},
  "source_lineage": {},
  "can_trade": false,
  "entry_authorized": false
}
```

Todos los tiempos de evidencia usados por un candidato deben ser menores o
iguales a `decision_time`. `candidate_id` se calcula sobre la identidad y los
hashes de fuente, no sobre labels de outcome futuros.
