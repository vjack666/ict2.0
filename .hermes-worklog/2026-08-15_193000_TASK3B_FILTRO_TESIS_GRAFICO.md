# Bitácora — Filtro BOS según tesis + gráfico mejorado (Task 3b)

**Fecha:** 2026-08-15 19:30 UTC-5
**Plan:** `.hermes/plans/2026-08-15_143000-individual-tools-m5-learning.md`
**Veredicto aplicado:** el filtro de tesis es PARTE DEL SISTEMA (no calificación humana). Fusión por nivel, is_unique, idle_bars, alineación HTF.

---

## Corrección del Agente Trader Humano (instrucciones escritas)
El Director detectó 5 errores en mi reporte previo:
1. Contar eventos en vez de setups (84 "active" eran 2 setups reales tras fusión).
2. Confundir `status=active` con "válido".
3. Ignorar BOS dormidos (12 días sin testear).
4. No aplicar definición de tesis (BOS = ruptura A FAVOR de la tendencia).
5. No fusionar por parent+precio.

Decisión: reemplazar tools/bos_filter.py por la versión canónica que el Director suministró, aplicando cascada:
geom ACTIVE → confirm_bars=2 → alineación HTF → fusión por (dir, price) → dormido.

## tools/bos_filter.py (versión canónica)
Campos anotados por evento en .extra:
- thesis_valid (bool), thesis_reason (str)
- is_unique (bool, representante del nivel fusionado)
- idle_bars (int), htf_aligned, htf_bias, fusion_count
Funciones: filter_bos_thesis(df, events, htf_frames, confirm_bars=2, max_idle_bars=288, ...) y summarize_bos_filter(events).

## Resultado sobre EURUSD M5 1 mes (2026-07-14→08-14)
Cascada:
- total_bos: 1609
- geometric_active: 84
- thesis_valid (confirm_bars=2 + HTF + NO dormido): 2
- unique_setups (tras fusión): 2 (1 up / 1 down)
Con max_idle_bars=288 (1 día): unique_setups = 0 (los 84 activos llevan ~12 días sin testear → todos dormidos).

HALLAZGO HONESTO: el número del mes es 2 (o 0 con dormido=1d), NO 5 como estimó el Director. El sistema corrigió la estimación con evidencia. El mes M5 tuvo un tramo donde el precio se fue y dejó la estructura latente 12 días.

## Gráfico mejorado (scripts/make_bos_chart.py + docs/charts/bos_cartesiano.html)
Mejoras tipo TradingView:
- Tema oscuro #131722, grilla #2a2e39.
- Candlestick con relleno + líneas 1px.
- Solo setups unicos en azul #2962ff (grosor 2.2); contexto en gris tenue.
- hovermode x unified; tickformat %d %H:%M (zoom nítido con hora).
- viewport + CSS en <style> (0 estilos inline, limpio para auditor).
- CLI: --max-idle, --all, --start, --end.

## Aislamiento mantenido
tools/bos_filter.py importa solo pandas + tools.event. No importa engine/.

## Siguiente
Commit [CERTIFICAR] + push de bos_filter.py, make_bos_chart.py, bos_cartesiano.html.
