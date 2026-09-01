# Worklog — Fase 0 Auditoría FVG/OB

**Fecha:** 2026-08-17 17:00 UTC-5  
**Fase:** 0 — Auditoría inicial  
**Hipótesis:** el motor ya contiene suficiente infraestructura Swing/BOS/CHOCH y FVG/OB parcial para evolucionar sin rehacer el sistema completo.  
**Resultado:** PASS CON BLOCKERS

## Objetivo

Conocer el flujo real del motor antes de modificarlo y determinar exactamente qué debe conservarse, unificarse o corregirse para incorporar FVG/OB como objetos causales.

## Evidencia revisada

- árbol completo de `main`;
- `engine/fvg_poi.py`;
- `engine/order_block.py`;
- `detectors/fvg.py`;
- `detectors/ob.py`;
- `engine/market_object.py`;
- `engine/lineage.py`;
- `engine/data_feed.py`;
- `engine/sequence.py`;
- `scripts/import_forex_data.py`;
- `docs/ict/03_FVG.md`;
- `docs/ict/04_ORDER_BLOCKS.md`;
- `docs/DATA_INVENTARIO.md`;
- `.gitignore`;
- `.hermes-index.md` y `.hermes-state/last_execution.json`.

## Hallazgos

1. Hay dos implementaciones de FVG y dos de OB.
2. La implementación OB de `detectors/ob.py` no coincide semánticamente con el canon documentado ni con `engine/order_block.py`; requiere resolución antes de producción.
3. FVG/OB tienen tracking limitado y no representan múltiples zonas persistentes con identidad.
4. `MarketObject` ya tiene identidad/linaje base, pero no un contrato explícito completo candidate/confirmation/tradable.
5. `engine/lineage.py` ya valida trazabilidad causal, pero FVG/OB todavía no son eslabones explícitos.
6. `engine/sequence.py` ya espera FVG/OB como entrada, pero los transporta principalmente como metadata de vela.
7. `data/` está ignorado por Git; el parquet no está disponible en el árbol remoto.
8. Existe discrepancia entre la ruta de datos documentada (`data/raw/SYMBOL/SYMBOL_TF.parquet`) y la ruta esperada por `engine/data_feed.py` (`data/raw/SYMBOL_TF.parquet`).
9. Persisten `engine/ote.py` y `detectors/fib.py`; se deben auditar imports antes de eliminarlos.
10. `00_HERMES_START_HERE.md`/`.hermes-index.md` apuntan a un nombre de archivo de umbrales incorrecto (`UMBRAL_CONFIRMACION.md` vs `UMBRALES_CONFIRMACION.md`).
11. No aparece un directorio `tests/` en el árbol de `main`; esto bloquea afirmar que existe una suite de aceptación completa.

## Tests/experimentos

No se ejecutaron tests de código en Fase 0 porque esta fase es de inspección y el entorno actual no contiene un checkout local ejecutable del repositorio. No se fabrican resultados.

## Decisión

**No tocar lógica de trading en Fase 0.**

Se pasa a Fase B sólo después de resolver los bloqueadores de contratos: detector canónico, dirección OB, representación temporal, suite de tests y ruta de datos.

## Documentación actualizada

- `docs/AUDITORIA_FASE0_FVG_OB.md`
- `.hermes-index.md` (debe reflejar este cierre)
- este worklog
- `docs/00_HERMES_START_HERE.md` debe corregir la ruta de `UMBRALES_CONFIRMACION.md` antes de ejecución autónoma.

## Commit de auditoría

`825f8da295fd4456e05fd51d796830369f356aac`

## Resultado

`PASS CON BLOCKERS`

### Bloqueadores para Fase B

- A0-01: unificar FVG/OB.
- A0-02: resolver semántica OB contra tesis.
- A0-04: completar contrato temporal de MarketObject.
- A0-10: localizar/reconstruir suite de tests.

### Siguiente acción exacta

Corregir la gobernanza documental del punto de entrada y comenzar **Fase B — Contratos de dominio**, sin implementar reglas nuevas hasta que el contrato sea único y testeable.
