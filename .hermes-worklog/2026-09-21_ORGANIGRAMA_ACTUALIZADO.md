# Bitacora — Organigrama actualizado contra imagen 2026-09-20

**Fecha:** 2026-09-21  
**Agente:** Codex / CEO operativo  
**Departamento:** D1 documentacion, D5 assurance  
**Estado:** `COMPLETED`

## Solicitud

Comparar el organigrama visual anterior enviado por Ruben con el estado real
actual y actualizar el organigrama del repositorio.

## Comparacion

La imagen anterior declaraba:

```text
Fecha: 20 Sep 2026
Estado global: EN DESARROLLO
Fase actual: Integracion Detectores -> MarketState
Progreso global estimado: ~35%
```

Estado actual tras Mision 1:

```text
Fecha de actualizacion: 21 Sep 2026
Fase actual: Mision 1 F2-F5 completada en shadow diagnostico
Progreso global estimado: ~72%
Siguiente hito: productor historico real seis-TF sobre fuente original
can_trade=false
```

## Cambios realizados

- `governance/ORGANIGRAMA_ICT_2_0.md`: nueva seccion comparativa contra la
  imagen 2026-09-20, con tabla de 11 bloques, semaforos y siguiente condicion.
- `governance/ORGANIGRAMA_ICT_2_0.mmd`: actualizado el grafo Mermaid para
  mostrar los 11 bloques operativos actuales junto a los departamentos D0-D7.
- `.hermes-index.md`: agregado resumen del cambio.

## Dictamen

El proyecto avanzo desde "Detectores -> MarketState" hacia un cableado completo
shadow:

```text
linaje seis-TF -> Episodes/Funnel -> backtest economico aislado
-> dataset causal IA -> baseline shadow
```

Este avance no declara edge, no crea modelo productivo, no habilita MT5 y no
autoriza trading.

