# Misión — Estrategia Simplificada: POI Canónica + Estocástico M15

**Misión:** MC-20260914-083000-poi-stoch-m15
**Estado:** INICIADA
**Fecha:** 2026-09-14
**Dueño:** Hermes (orquestador) + Rubén (autoridad final para activación de órdenes)
**Modo:** LOCAL_ONLY

## Resumen ejecutivo

Simplificar la estrategia para que una entrada dependa de:
1. **Proximidad a una POI canónica** (FVG o OB con identificador, límites, dirección, estados).
2. **Confirmación mediante estocástico M15 cerrado** (14,3,3; cruce desde sobreventa para compra, desde sobrecompra para venta).

Las demás lecturas técnicas (H4/H1, sweep, displacement, BOS/CHoCH, retest, M5/M1 como confirmación, umbral 70% probabilidad) permanecen como **contexto** y dejan de bloquear esta estrategia.

La activación de órdenes requiere decisión posterior del usuario.

## Líneas que deben mantenerse separadas

| Línea | Responsable | Estatus |
|---|---|---|
| Implementación técnica | D2 Ingeniería | Esta misión |
| Evidencia económica | D6 Research + D4 Datos | Pendiente, bajo contrato propio |
| Autorización operativa | Rubén | Explota después de auditoría D5 |

## Orden de ejecución

1. Inventario de bloqueos (D2) — INICIO INMEDIATO
2. En paralelo: especificación (D6) + contrato POI (D2) + reloj MT5 (D4)
3. Evaluador POI + estocástico M15 (D2) — espera 1 y 2
4. Adaptación del bot (D2) — espera 3
5. Interfaz (D7) — espera 4
6. Pruebas técnicas y causales (D5) — espera 4
7. Evaluación histórica (D6+D4) — espera 3 (puede empezar con datos)
8. Auditoría independiente (D5) — espera 6 y 7
9. Cierre (Hermes+D1) — espera 8

## Invariantes no negociables

- `engine/` NO importa `backtest/`. Ley fundamental.
- La evaluación histórica usa datos existentes e inmutables, bajo contrato propio.
- Ninguna prueba envía órdenes reales o DEMO.
- `Apagar` sigue siendo desarme que impide nuevas entradas sin liquidar posiciones.
- Esta misión no modifica volúmenes, reentradas, SL/TP ni cierre del ciclo.
- El motor canónico conserva su contrato observacional; esta estrategia es un camino adicional de entrada, no una reescritura del motor.

## Entregables

Ver 12 puntos de la misión original. Cada trabajador devuelve: `AGENTE`, `DEPARTAMENTO`, `TAREA`, `STATUS`, `EVIDENCIA`, `ARCHIVOS`, `RIESGOS`, `SIGUIENTE ACCIÓN`.
