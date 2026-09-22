# ICT_MULTIMODEL_CANDIDATE_V1

**Estado:** `IMPLEMENTED_IN_BACKTEST_DIAGNOSTIC`
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

## Implementación diagnóstica Misión 7

El backtest six-TF ya materializa una clasificación equivalente por episodio en
`entry_protocols`:

- `PO3` mediante `engine.po3.build_po3_state`.
- `SILVER_BULLET` mediante `engine.silver_bullet.is_silver_bullet`.
- `TURTLE_SOUP` mediante `engine.turtle_soup.is_turtle_soup`.

La salida está registrada en
`reports/audits/experiments/mission7/sixtf_episode_backtest_entry_protocols_2022_03_w2.json`
y en la caja negra JSONL correspondiente. Esta implementación no es todavía el
schema persistente final de candidato multimodelo; es el primer consumidor
diagnóstico integrado al backtest.

Resultado de referencia 2022-03-07..2022-03-13:

- PO3 completo: 121/121.
- Silver Bullet completo: 0/121.
- Turtle Soup completo: 0/121.
- IA shadow aceptó 40/121 para análisis tras sesión/protocolo.
- El subconjunto aceptado siguió negativo (`mean_net_R=-0.4300`).

Por tanto, el contrato queda implementado en ruta diagnóstica, pero pendiente
de calibración semántica, deduplicación por evento económico y medición formal
contra `FREQ_GATE_2_3_WEEKLY_V1`.
