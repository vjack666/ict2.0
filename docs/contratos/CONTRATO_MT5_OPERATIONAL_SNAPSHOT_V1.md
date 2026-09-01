# Contrato — Snapshot operativo MT5 v1

**Estado:** NORMATIVO PARA IMPLEMENTACIÓN LOCAL
**Fecha:** 2026-08-31
**Propósito:** cerrar la frontera entre el feed local de MT5 y la lectura causal
del motor, sin convertirla en ejecución financiera.

## 1. Objetivo

Construir una única salida de lectura para el mercado actual:

```text
MT5 local → barras normalizadas → Context State → objetos canónicos →
Lifecycle/MarketState → Wyckoff como evidencia → snapshot diario
```

La salida debe responder qué se conocía en `decision_time`, usando únicamente
velas cerradas, y debe ser reproducible con los mismos archivos, configuración y
commit.

## 1.1 Separación de planos de datos

El proyecto mantiene dos feeds deliberadamente distintos:

| Plano | Fuente | Uso autorizado | No significa |
|---|---|---|---|
| Investigación | Dukascopy histórico | funnel, análisis, backtest y tests generales | no es feed operativo ni reemplaza MT5 |
| Operación | MT5 local | actualizar la punta actual, snapshot diario y futura ejecución | no es evidencia histórica del funnel ni autoriza órdenes por sí solo |

No se mezclan ni se sustituyen silenciosamente. La frescura del parquet MT5
prueba actualidad operativa; la reproducibilidad de Dukascopy prueba una
investigación histórica. Son gates diferentes y cada reporte debe identificar
el plano que está auditando.

## 2. Fronteras de autoridad

| Concepto | Autoridad |
|---|---|
| adquisición y actualización de parquet | `scripts/daily/update_mt5_ict.py` |
| corte de vela cerrada y frescura | `scripts/daily/brief_lunes.py` |
| Context State multinivel | `engine.mtf_navigation` |
| objetos FVG/OB y relaciones | detectores y relaciones canónicos |
| estado histórico por objeto | `engine.market_state.MarketState` |
| ciclo de vida | `engine.lifecycle` |
| lectura Wyckoff | `engine/Wyckoff` |
| presentación | `engine.daily_motor` / brief diario |

`engine.mtf_navigation.MarketState` se denomina **Context State** en esta
frontera. `engine.market_state.MarketState` se denomina **Object MarketState**.
No se fusionan las clases ni se crea una tercera clase con el mismo significado.

## 3. Reglas temporales

- `decision_time` es UTC y solo acepta barras cerradas.
- Cada timeframe usa `closed_bar_cutoff(as_of, tf)`.
- Ningún objeto con `creation_time > decision_time` entra en el snapshot.
- `authority_tf == lifecycle_tf == origin_tf` se conserva para el estado oficial.
- Una observación LTF puede quedar en `meta["observations"]`, pero no puede
  modificar el estado oficial de un objeto HTF.
- Un dato atrasado o fuera de orden falla cerrado; no se reordena en silencio.

## 4. Salida mínima

El snapshot operativo debe conservar:

```text
schema_version, symbol, source=MT5_LOCAL, decision_time,
asof_times_by_tf, source_files, source_hashes, worktree/commit,
context_state, object_market_state, canonical_zones, sequence,
wyckoff, lineage_refs, status, policy=OBSERVE_ONLY_NO_ORDER
```

La salida de esta versión es descriptiva. No contiene orden, fill, broker,
sizing, PnL ni `entry_authorized=True`. La futura emisión de órdenes será una
misión posterior, con contrato propio, usando el snapshot MT5 como entrada y
sus gates de seguridad; no se activa automáticamente al cerrar este puente.

## 5. Prohibiciones

- No descargar ni modificar Dukascopy durante esta etapa operativa; el feed
  histórico permanece reservado al plano de investigación.
- No sustituir MT5 por otra fuente ni mezclar feeds sin declarar contrato.
- No recalcular FVG/OB, Sequence, AHF o Lifecycle en el adaptador.
- No usar el `MarketState` presente cuando se requiere `T`.
- No ejecutar backtest de rendimiento, entrenar IA ni promover a producción.

## 6. Gates

1. Inventario de consumidores y ausencia de tercera autoridad.
2. Frescura de todos los TF requeridos y exclusión de vela abierta.
3. Snapshot serializable con hashes, commit, configuración y timestamps.
4. Autoridad TF y lineage conservados.
5. Inmutabilidad de entradas y política `OBSERVE_ONLY_NO_ORDER`.
6. FULL/PREFIX causal para varios `decision_time` sobre fixtures sintéticos.
7. Determinismo: mismo input/config/commit produce el mismo contenido lógico.
8. Tests focales, suite completa, worklog, índice, Graphify y commit local.

`PASS` aquí certifica la lectura mecánica y causal del snapshot. No certifica
edge, rentabilidad, ejecución ni permisos de mercado.
