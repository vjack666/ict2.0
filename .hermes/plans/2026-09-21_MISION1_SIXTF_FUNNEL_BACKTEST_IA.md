# Plan ejecutable — Mision 1 seis-TF -> Funnel -> Backtest -> IA

**Fecha:** 2026-09-21  
**Estado:** `F0_F1_COMPLETED / F2_READY`  
**SDD:** `docs/planificacion/SDD_MISION1_SIXTF_FUNNEL_BACKTEST_IA_V1.md`  
**Contratos base:** `CONTRATO_LINEAGE_HIERARCHY_V1`, `CONTRATO_EPISODES_FUNNEL_V1`  
**Politica:** `LOCAL_ONLY`, `can_trade=false`, sin nuevas ramas, sin push salvo instruccion explicita.

## Objetivo

Convertir el cierre PR16 de linaje seis-TF en una ruta ejecutable hacia:

```text
episodios seis-TF causales -> backtest funnel -> dataset IA -> entrenamiento shadow
```

## Fase cerrada ahora

### F0 — Buscar base reutilizable

- [x] Revisar indice maestro.
- [x] Revisar SDD Episodes/Funnel v1.
- [x] Revisar Contrato Episodes/Funnel v1.
- [x] Revisar Contrato Lineage Hierarchy v1.
- [x] Consultar Graphify para la relacion lineage/episodes/funnel.
- [x] Confirmar PR16 mergeado remoto como autoridad previa.

Resultado: existe base reutilizable; no se crea un segundo funnel.

### F1 — Crear puente post-PR16

- [x] Definir SDD de Mision 1.
- [x] Congelar no-regresion seis-TF: no H4/M15 como contexto principal.
- [x] Separar fase documental de implementacion, backtest y entrenamiento.
- [x] Definir gates M1-G0..M1-G7.
- [x] Declarar bloqueos actuales sin sobrescribir cambios locales.
- [x] Actualizar indice y bitacora.

Resultado: fase documental/preflight completada al 100%.

## Fase siguiente: F2

Implementar o certificar el productor seis-TF hacia `engine/episodes.py`.

Tareas:

1. Trabajar sobre una base local segura que contenga PR16 sin destruir cambios sucios.
2. Adaptar `engine/episodes.py` o su runner para exigir lineage jerarquico valido.
3. Ejecutar FULL/PREFIX literal de episodios con seis TF.
4. Publicar reporte de aceptados/rechazados y razones.
5. Correr suite focal + grupo causal.
6. Actualizar Graphify, indice, bitacora y commit selectivo.

## No-go

- No entrenar IA hasta F4/F5.
- No backtest economico hasta F3.
- No declarar edge.
- No conectar MT5.
- No usar M1 inexistente por inferencia.
- No crear ramas nuevas.

