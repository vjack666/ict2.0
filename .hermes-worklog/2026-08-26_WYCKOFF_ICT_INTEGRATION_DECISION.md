# Decisión — siguiente fase: integración ICT + Wyckoff existente

**Fecha:** 2026-08-26
**Agente:** Codex, CEO operativo
**Departamento:** Dirección/gobierno + CTO/D2 + Research/D6
**Status:** `COMPLETED` como decisión; implementación pendiente de gates.

## Decisión

La siguiente fase parte del motor ICT/AHF y del módulo `engine/Wyckoff` ya
existentes. Se completará el evaluador Wyckoff dentro de esa arquitectura; no
se construirá un segundo motor, otra AHF ni una autoridad paralela.

ICT conserva la autoridad sobre Swing, BOS/CHOCH, liquidez, FVG/OB, Sequence,
POI, Context State y lineage. Wyckoff consume sus snapshots/referencias en
modo read-only y devuelve evidencia de rango/fase/eventos, volumen/OI y
alineación, sin mutar dirección, estados, zonas ni autorización de entrada.

## Orden de la fase

1. Congelar interfaces ICT/AHF e inventariar referencias.
2. Completar el contrato de entrada de `engine/Wyckoff`.
3. Implementar eventos/transiciones faltantes en el módulo existente.
4. Integrar `WyckoffEvidence` con lineage y timestamps PIT.
5. Ejecutar fixtures sintéticos de rangos, secuencias, solapamientos y
   FULL/PREFIX.
6. Repetir auditoría independiente.

La ausencia de CME `6E`/OI mantiene bloqueada la certificación de datos y el
nuevo experimento. Esta decisión arquitectónica no autoriza entrenamiento,
backtest, promoción ni órdenes.
