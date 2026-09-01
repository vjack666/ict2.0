# Worklog — Auditoría temporal AHF / MTF

**Fecha:** 2026-08-19  
**Estado:** DISEÑO ENTREGADO / EJECUCIÓN PENDIENTE

## Objetivo

Auditar el tiempo y la trayectoria del AHF antes del backtest: cuánto tarda en resolver cada condición, cuánto permanece en cada estado, cuándo desciende de timeframe, cuándo retrocede por invalidación, cuántas velas retrocede, cuánto tarda en reconfirmar y si existen estados atascados o ciclos de indecisión.

## Decisión metodológica

La auditoría se modela como análisis de **duración/holding time + transiciones de estados**, más cercano conceptualmente a un proceso semi-Markov que a un loop fijo. Esto permite estudiar no sólo qué estado se visita, sino cuánto dura y hacia qué estado transiciona. La literatura financiera sobre procesos semi-Markov muestra precisamente que las duraciones de estado pueden contener información que un modelo de transición sin duración pierde. 

## Entregas

- `docs/AUDITORIA_TEMPORAL_AHF_MTF.md`
- `audits/codigo/ahf_temporal_navigation_audit.py`

## Métricas obligatorias

- latencia hasta condición por capa;
- duración de cada estado;
- tiempo de descenso entre TF;
- tiempo hasta `SETUP_READY`;
- número y profundidad de rollbacks;
- velas desde invalidación hasta retorno;
- tiempo hasta reconfirmación;
- número de revisitas por TF;
- switches upward/downward;
- profundidad máxima alcanzada;
- estados atascados;
- reescritura de contexto LOCKED;
- violaciones PIT/as-of.

## Resultado actual

No se declara ningún PASS empírico todavía. La auditoría está formalizada y lista para ejecutarse sobre traces reales del AHF.

## Gate

El backtest multi-TF permanece bloqueado hasta obtener un trace temporal completo, pasar TNA-01→TNA-06 y resolver cualquier defecto de navegación o causalidad que aparezca.