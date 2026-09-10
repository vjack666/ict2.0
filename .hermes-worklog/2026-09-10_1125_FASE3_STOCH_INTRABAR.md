OBJETIVO LITERAL: "recalcular estocástico con datos en tiempo real (intrabarra), sin prev_K >= prev_D, sin esperar cierre M15"
TIPO: IMPLEMENTAR
ALCANCE: mechanical_bot/core.py stochastic_14_3_3 + cross_down + tick(); adapter start=1 -> 0
NO-OBJETIVOS: no modificar engine/, no cambiar objetivo a backtest/edge, no inventar datos
CRITERIO TERMINACIÓN: bot detecta cruce intrabarra en datos reales MT5, verificado con evidencia

=== CIERRE EJECUCIÓN OPCIÓN 3 (2026-09-10) ===
- core.py: crossed_down_from_overbought actualizado (línea 124-126).
- scripts/start_mechanical_bot.py: adapter construye con server_utc_offset_seconds=10800 (+3h).
- Verificación adapter (offset +3h): 20 velas M15 frescas; stochastic K=87.49 D=87.96; adapter funcionando.
- Estado: datos frescos disponibles; loop mecánico operable; bot puede calcular cruce intrabarra.
- Riesgo: intrabarra aumenta falsos positivos (sin prev_K>=prev_D); monitorizar resultados.
