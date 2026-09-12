# Contrato — Grafo de navegación multi-TF (Context State)

> Enmienda vigente de Ruben (2026-09-11): se autoriza avanzar autonomamente con entrenamiento y evaluacion de IA sobre datos existentes e inmutables. No se requiere una nueva autorizacion humana para cada fase. La ausencia de licencia o permiso escrito de Dukascopy deja de ser un bloqueo interno y no se solicitara licencia. Rige `docs/contratos/ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md` sobre las restricciones anteriores de este documento. Los controles tecnicos se verifican durante el trabajo; sus fallos se reportan sin alterar datos ni fabricar certificaciones. Esta autorizacion no habilita trading ni promocion automatica a produccion.


**Estado:** NORMATIVO v1  
**Módulo:** `engine/mtf_navigation.py`  
**SDD padre:** `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`

## Qué implementa

```text
D1  → HAS_RELEVANT_CONTEXT
H4  → WHERE_IN_CONTEXT (premium / equilibrium / discount)
H1  → HAS_STRUCTURE + depth proxy
LTF → HAS_TRIGGER (proxy) / WAITING_RETEST (opcional)
        ↓
ContextConstraints (mapa de restricciones)
```

## Qué NO implementa

- Señales de entrada / órdenes / PnL  
- Bias por EMA  
- Entrenamiento de IA ni “paseo” autónomo con labels buy/sell  
- Secuencia completa liq→…→retest (sigue en `sequential_events.py`; el grafo expone un *proxy* de profundidad)

## Anti-look-ahead

`asof_bar` = última barra con `time <= decision_time` en cada TF.

## Gate v1

- tests `tests/test_mtf_navigation.py` PASS  
- `constraints.policy == CONTEXT_ONLY_NOT_ENTRY`  
- smoke H1 20Y documentado sin claim de edge  
