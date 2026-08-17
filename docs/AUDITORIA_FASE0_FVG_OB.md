# AUDITORÍA FASE 0 — FVG + ORDER BLOCKS

**Fecha:** 2026-08-17  
**Estado:** COMPLETADA — GATE A: PASS CON BLOCKERS TÉCNICOS DOCUMENTADOS  
**Alcance:** auditoría previa a implementación; no se modifica lógica de trading en esta fase.

## 1. Objetivo

Mapear el estado real del repositorio antes de implementar el plan FVG/OB: arquitectura, detectores existentes, objetos de mercado, secuencia, datos, OTE residual, temporalidad y puntos de integración.

## 2. Inventario real relevante

### Estructura

- `engine/`: fuente de decisión del motor.
- `detectors/`: detectores base, incluyendo `fvg.py`, `ob.py`, `displacement.py`, `liquidity.py`, `bos.py`, `choch.py`.
- `tools/`: herramientas/eventos y Swing/BOS/CHOCH.
- `engine/sequence.py`: memoria secuencial y ensamblaje de eventos.
- `engine/market_object.py`: ontología `MarketObject`.
- `engine/lineage.py`: auditoría de trazabilidad causal.
- `scripts/`: generación de datasets, walk-forward y aprendizaje.

No se encontró un directorio `tests/` en el árbol de `main` auditado. Esto debe considerarse un riesgo para el Gate C/D y se debe localizar/reconstruir la suite efectiva antes de implementar.

## 3. Hallazgo crítico #1 — existen DOS implementaciones FVG/OB

### FVG

Existen:

- `detectors/fvg.py`
- `engine/fvg_poi.py`

Ambas detectan FVG de tres velas, pero tienen responsabilidades distintas y no deben evolucionar en paralelo sin contrato de autoridad.

`engine/fvg_poi.py` añade anclaje HTF y asociación con BOS, mientras `detectors/fvg.py` añade `pd_type/pd_tier` y tracking básico.

**Riesgo:** divergencia semántica entre detector base y motor.

### OB

Existen:

- `detectors/ob.py`
- `engine/order_block.py`

La divergencia es más grave que en FVG.

`engine/order_block.py` implementa el canon documentado como: vela contraria + cuerpo fuerte + follow-through siguiente (`shift(-1)`), con la advertencia de que sólo puede consumirse después de la confirmación.

`detectors/ob.py` contiene una implementación distinta que usa la vela actual y `prev_high/prev_low`, y además su naming/comentario de dirección no coincide con el contrato de `docs/ict/04_ORDER_BLOCKS.md`.

**Conclusión:** NO seleccionar una implementación por intuición. La Fase B debe fijar un contrato único y la Fase C debe eliminar/aislar la implementación contradictoria.

## 4. Hallazgo crítico #2 — clasificación OB incompleta/inconsistente

`detectors/ob.py` ya tiene metadatos para:

- `OB`;
- `REJECTION_BLOCK`;
- `PROPULSION` implícito en comentarios;
- `MITIGATION_BLOCK` y `BREAKER` previstos para resolver posteriormente.

Pero no existe todavía una representación de dominio completa que conserve la genealogía de cada transformación.

**Necesidad:** `OB → invalidation/structure event → BREAKER` debe ser una relación explícita, no una etiqueta sobrescrita.

## 5. Hallazgo crítico #3 — lifecycle FVG/OB demasiado limitado

El tracking actual mantiene esencialmente un FVG bullish y uno bearish activos a la vez y un único OB vigente por dirección.

Esto no permite representar correctamente múltiples zonas coexistentes, stacking ni historial de mitigaciones.

**Impacto:** insuficiente para aprendizaje causal y para BPR/stacking multi-TF.

## 6. Hallazgo crítico #4 — MarketObject aún no contiene todo el contrato temporal requerido

`engine/market_object.py` ya aporta identidad, `origin_tf`, `role`, `direction`, zona, `creation_time`, estado, `parent_object`, `related_objects`, `bar_index` y `bar_time`.

Faltan como campos explícitos del objeto:

- `candidate_time` / `candidate_bar`;
- `confirmation_time` / `confirmation_bar`;
- `tradable_time` / `tradable_bar`;
- información explícita de mitigación/invalidación cuando corresponda.

Parte de esa información puede existir en `meta`, pero para el contrato FVG/OB debe quedar definida y testeable.

## 7. Hallazgo crítico #5 — lineage existente es buena base, pero la cadena actual no contempla FVG/OB como eslabones explícitos

`engine/lineage.py` valida la cadena canónica:

`LIQUIDITY → SWEEP → DISPLACE → BOS → POI → REFINEMENT → RETURN`

La infraestructura de `MarketObject.parent_object` es adecuada para extenderla, pero FVG/OB deben entrar como objetos causales explícitos, no sólo como columnas de una vela.

Objetivo:

`LIQUIDITY → SWEEP → DISPLACE → BOS/CHOCH → FVG/OB → POI/REFINEMENT → RETURN → CONTRACT`

## 8. Hallazgo crítico #6 — secuencia ya espera FVG/OB

`engine/sequence.py` declara que la entrada aparece cuando existe FVG/OB después de la secuencia de sweep → displacement → BOS/CHOCH y transporta campos `fvg_*`, `ob_*` y `pd_type/pd_tier` dentro del contexto de cada vela.

Esto confirma que la integración ya existe parcialmente, pero está basada en features por vela, no en objetos FVG/OB con identidad y lifecycle.

**Conclusión:** la nueva implementación debe reemplazar gradualmente esa dependencia por objetos sin romper compatibilidad durante la migración.

## 9. Hallazgo crítico #7 — fuente de datos no está versionada en Git

`data/` está explícitamente ignorado por `.gitignore`.

`docs/DATA_INVENTARIO.md` indica que existen raw EURUSD D1/H1/H4/M1/M3/M5/M15 y que contienen OHLC + `tick_volume` + `spread`.

El archivo `data/raw/EURUSD_M5.parquet` solicitado no está en el árbol de GitHub auditado. Por tanto, no puede auditarse su contenido desde GitHub en esta sesión.

Esto NO es necesariamente un problema del proyecto: el diseño indica que los binarios se mantienen fuera del repo. Pero el entorno de ejecución de Hermes debe comprobar su presencia local antes de backtests.

## 10. Hallazgo crítico #8 — inconsistencia de ruta de datos

`docs/DATA_INVENTARIO.md` y `scripts/import_forex_data.py` describen la estructura:

`data/raw/EURUSD/EURUSD_M5.parquet`

pero `engine/data_feed.py` busca:

`data/raw/EURUSD_M5.parquet`

El nombre plano coincide con el archivo solicitado por el usuario, pero no con la estructura documentada de importación.

**Decisión:** antes del backtest real, Hermes debe resolver esta discrepancia mediante un contrato único de ruta o un loader compatible con ambas formas. No se debe declarar el dataset disponible sólo porque el inventario lo enumere.

## 11. Hallazgo crítico #9 — OTE todavía existe físicamente

El árbol contiene `engine/ote.py` y `detectors/fib.py`.

La documentación vigente prohíbe OTE. No se encontró en esta auditoría evidencia suficiente para afirmar que ambos módulos sigan siendo consumidores activos del pipeline, por lo que **no se deben borrar ciegamente en Fase 0**.

Acción de Fase B/C: auditar imports/referencias y retirar módulos si están muertos; si algún consumidor existe, eliminarlo o migrarlo. No reintroducir OTE bajo otro nombre.

## 12. Hallazgo crítico #10 — error documental en la ruta de umbrales

`docs/00_HERMES_START_HERE.md` y `.hermes-index.md` referencian `docs/UMBRAL_CONFIRMACION.md`, pero el archivo real del repo es:

`docs/UMBRALES_CONFIRMACION.md`

Esto rompe el punto de entrada documental de Hermes y debe corregirse antes de delegar la ejecución autónoma.

## 13. Arquitectura real observada

```text
RAW OHLC
  ↓
Data Feed
  ↓
Detectors / Tools
  ├── Swing
  ├── BOS / CHOCH
  ├── Liquidity / Sweep
  ├── Displacement
  ├── FVG
  └── OB
  ↓
MarketObject / Candle meta
  ↓
SequenceState
  ↓
POI / Zone Authority / Execution
  ↓
Signal / Expediente
  ↓
Learning / Backtest
```

La arquitectura objetivo debe insertar objetos FVG/OB persistentes entre displacement/structure y POI, manteniendo compatibilidad temporal con `sequence.py`.

## 14. Riesgos prioritarios

| ID | Riesgo | Severidad | Acción |
|---|---|---|---|
| A0-01 | Dos detectores FVG/OB con semánticas distintas | CRÍTICA | Unificar contrato |
| A0-02 | OB direction/algoritmo divergente | CRÍTICA | Resolver contra tesis |
| A0-03 | Tracking sólo de zonas activas limitadas | ALTA | Lifecycle multi-zona |
| A0-04 | MarketObject sin contrato temporal completo | CRÍTICA | Añadir campos/metadata |
| A0-05 | Lineage no incluye FVG/OB explícitos | ALTA | Extender genealogía |
| A0-06 | Dataset no versionado en repo | MEDIA | Validar entorno |
| A0-07 | Ruta raw documentada ≠ ruta del loader | ALTA | Unificar |
| A0-08 | OTE residual en módulos | ALTA | Auditar imports y retirar |
| A0-09 | Ruta incorrecta de UMBRALES en documentación | ALTA | Corregir antes de Hermes |
| A0-10 | No aparece `tests/` en árbol auditado | CRÍTICA | Localizar/reconstruir suite |

## 15. Decisiones de Fase 0

1. **No modificar detectores todavía.**
2. `docs/ict/SPEC_TESIS_FORMAL.md` + enmienda OTE siguen siendo autoridad.
3. La implementación canónica FVG/OB debe quedar en `engine/` como fuente de decisión, pero puede reutilizar `detectors/` como capa de detección si se demuestra equivalencia y se elimina la divergencia.
4. `MarketObject` será la representación persistente de FVG/OB.
5. `sequence.py` será adaptado después de cerrar los contratos de dominio.
6. No se empieza aprendizaje/ablación hasta que la semántica y temporalidad de FVG/OB estén cerradas.

## 16. Gate A

**PASS CON BLOCKERS DOCUMENTADOS.**

La arquitectura real está suficientemente identificada para comenzar la Fase B, pero **no se debe iniciar implementación de producción hasta resolver los bloqueadores A0-01, A0-02, A0-04 y A0-10**.

La auditoría no modifica lógica de trading.
