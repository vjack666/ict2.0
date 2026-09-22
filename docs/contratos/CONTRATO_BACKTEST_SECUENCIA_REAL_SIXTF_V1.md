# Contrato — Backtest six-TF con secuencia real M1 v1

**Estado:** NORMATIVO PARA MISIÓN 6
**Fecha:** 2026-09-22

## Propósito

El backtest six-TF no puede aceptar episodios únicamente por linaje sintético.
Debe consultar el motor secuencial real (`engine.sequential_events`) y adjuntar
evidencia multi-bar cerrada antes de `decision_time`.

## Reglas

- La evidencia real mínima es una cadena `COMPLETE`:
  `LIQUIDITY_POOL -> SWEEP -> DISPLACEMENT -> STRUCTURE -> OB -> FVG -> RETEST`.
- Las barras de la cadena deben ser estrictamente crecientes.
- La cadena debe terminar en o antes de `decision_time`.
- La dirección de la cadena debe coincidir con el episodio.
- Si existe cadena real válida, la compresión sintética del conector deja de
  bloquear el episodio; queda solo como contexto diagnóstico.
- Futuro, HTF no cerrado u orden temporal imposible siguen siendo bloqueo.

## Caja negra

Cada corrida debe poder emitir JSONL append/readable por episodio con:

- `episode_id`, `decision_time`, `exit_status`, `net_R`, sesión;
- veredicto forense y cadena secuencial usada;
- clasificación de protocolos de entrada de tesis: PO3, Silver Bullet y Turtle
  Soup, siempre como diagnóstico;
- decisión IA shadow;
- política `can_trade=false`, `orders_sent=false`, `mt5_connected=false`.

## Protocolos de entrada de tesis

Desde la Misión 7, el backtest consume los módulos existentes:

- `engine.po3.build_po3_state`;
- `engine.silver_bullet.is_silver_bullet`;
- `engine.turtle_soup.is_turtle_soup`;
- `engine.killzone.killzone_en`.

La clasificación de familias (`PO3`, `SILVER_BULLET`, `TURTLE_SOUP`) no crea
órdenes ni cambia el motor. Si ninguna familia completa está presente, la IA
shadow debe abstenerse aunque la secuencia M1 sea causalmente válida.

## Trabajadores por temporalidad

El backtest puede publicar evidencia diagnóstica de trabajadores lógicos sin
crear motores nuevos:

- D1/H4/H1/M15/M5: `engine.mtf_navigation.MTFNavigator`.
- M1: `engine.sequential_events.run_sequential`.
- Coordinador: runner forense del backtest.

La evidencia de trabajadores es un mapa de contexto y trazabilidad. No es una
señal de entrada y no autoriza trading.

## Límite

Este contrato corrige la auditoría temporal del backtest. No declara edge ni
reduce por sí solo la frecuencia a 2–3 trades/semana.
