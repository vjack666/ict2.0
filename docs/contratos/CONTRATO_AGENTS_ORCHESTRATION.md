# Contrato de agentes y orquestación

**Estado:** NORMATIVO — arquitectura de aplicación
**Fecha:** 2026-08-20

## Autoridad

Los agentes interpretan y explican el mercado, pero no redefinen las
autoridades del motor:

| Concepto | Única autoridad |
|---|---|
| Context State | `engine/mtf_navigation.py` |
| AHF | `engine/ahf.py` |
| FVG/OB causal | `engine/detectors/` + `engine/market_object.py` |
| Sequence | `engine/sequential_events.py` |
| Lineage | `engine/lineage.py` |
| LTF diario | `engine/daily_motor.py` |
| Wyckoff | `engine/Wyckoff/` |
| Presentación | `scripts/daily/brief_lunes.py` |

## Capas activas

```text
engine snapshot canónico
        ↓
agents/ API pública estable
        ↓
analysis/ interpretación y evidencia
        ↓
orchestration/ coordinación y agregación
        ↓
lectura diaria o experimento
```

`agents/` y `orchestration/` son capas activas. No se consideran legacy por
ser fachadas o por conservar compatibilidad.

## Prohibiciones

Un agente u orquestador no puede:

- crear un segundo Context State, AHF, Sequence o Wyckoff runtime;
- cambiar la dirección del snapshot canónico;
- crear FVG/OB paralelos con otra semántica;
- usar futuro o datos posteriores al `decision_time`;
- convertir `SETUP_READY` en una orden;
- promover una predicción IA sin gate y shadow mode;
- importar módulos prohibidos o cuarentenados.

## Compatibilidad

Los métodos actuales basados en `DataFrame` se conservan como API compatible.
La evolución debe añadir adaptadores para `CanonicalSnapshot` sin romper
`agents.*`, `analysis.*` ni `orchestration.*`.
