# Arquitectura de detectores — dos interfaces intencionales

**Fecha:** 2026-08-19
**Decisión:** mantener DOS implementaciones de FVG/OB; NO unificar.

## Las dos interfaces

| Ruta | Interfaz de salida | Consumidores | Rol |
|------|--------------------|--------------|-----|
| `detectors/fvg.py` · `detectors/ob.py` (raíz) | `pd.DataFrame` con columnas por barra (`fvg_bullish`, `fvg_mid`, `ob_top`, `ob_bottom`, `fvg_fill_status`, `ob_status`, `pd_type`, `pd_tier`) | `engine/market_features.py`, `engine/htf_pd_index.py` | Feature-frame por vela (lo lee la capa de consenso `analysis/*` y el motor de estructura) |
| `engine/detectors/fvg.py` · `engine/detectors/ob.py` | `list[MarketObject]` (objetos discretos con `zone_high`/`zone_low`/`bar_index`/`state`) | `engine/sequential_events.py`, `engine/sequence.py`, `audits/codigo/*` | Motor de secuencia de eventos (causalidad, lineage, relations) |

## Por qué NO es duplicación

No son dos copias de lo mismo con distinto nombre. Cubren **necesidades
distintas** del motor:

1. La capa de consenso (agentes ICT/Wyckoff/Structure/Decision) y
   `engine.market_features.build_features` operan sobre un **DataFrame de
   features por barra** — necesitan flags booleanos y niveles por vela
   (`fvg_bullish[i]`, `ob_top[i]`, `fvg_fill_status[i]`).
2. El motor de secuencia de eventos (`engine/sequence.py` +
   `engine/sequential_events.py`) opera sobre **objetos de mercado discretos**
   (`MarketObject`) con linaje causal y estado de mitigación/invalidación.

Migrar `market_features.py`/`htf_pd_index.py` a `list[MarketObject]` implicaría
reescribir el consumo de columnas `fvg_*`/`ob_*` en toda la capa de consenso —
rework grande con riesgo de romper agentes que hoy funcionan. No aporta edge;
solo riesgo.

## Regla de convivencia

- `detectors/` (raíz) = fuente de features DataFrame. No se toca salvo que se
  cambie la semántica de columnas del contrato de features.
- `engine/detectors/` = fuente de objetos del motor de eventos. Canónica para
  `sequence`/`sequential_events`/`relations`.
- Si algún día se unifica, el adaptador debe ser `list[MarketObject] ->
  DataFrame`, no al revés (el DataFrame es el contrato de la capa de consenso).

## Nota sobre `fase-c-domain` (rama de la nube)

La rama `origin/agent/fase-c-domain` (HEAD `94ab410`, 2026-08-17) quedó
**obsoleta**: diff contra `main` = 108 archivos borrados, 0 nuevos netos. No
aporta nada que `main` no tenga ya — de hecho `main` contiene versiones más
recientes de todo, incluidos `engine/detectors/fvg.py`+`ob.py` ya implementados.
Por eso **no se fusionó**: habría destruido trabajo. Sus detectores FVG/OB
canónicos ya estaban presentes en `main`.
