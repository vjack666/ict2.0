# Decisión pendiente — parámetros económicos del baseline Edge intradía

**Fecha:** 2026-09-02  
**Estado:** `DRAFT_FOR_CLIENT_FREEZE`  
**Experimento:** `EXP-PASS-EDGE-INTRADIA-01`  
**Alcance:** investigación local; sin IA, órdenes ni promoción

## Recomendación ejecutiva

Usar un único contrato primario conservador y congelarlo antes de ejecutar:

| Campo | Recomendación para el baseline |
|---|---|
| Entrada | retorno a FVG/OB M15 después de sweep + BOS/CHOCH, dentro de London/NY |
| Stop | mecha del sweep M15 ± `0,3 ATR`, con el límite normativo de tamaño ya definido |
| TP | liquidez opuesta M15 más cercana, solo si RR `>= 1:3` |
| Fill | primer toque observable de la zona en una barra EXEC posterior; precio de toque, no cierre de barra |
| Salida | `FIRST_TOUCH_TIMEOUT`: TP/SL por toque; timeout fijo preregistrado; sin cierre parcial |
| TP y SL en la misma vela | prioridad conservadora `SL_FIRST` cuando OHLC no permite ordenar intrabar |
| Coste primario | usar spread observable cuando exista; donde no exista, declarar proxy fijo y reportarlo separadamente |
| Slippage | valor fijo preregistrado, separado del spread |
| Comisión | valor explícito por lote; nunca asumir cero sin declararlo como escenario |

## Decisiones que todavía requieren congelación

La tesis fija la mecánica ICT, pero no fija los valores económicos universales.
Antes de correr el baseline hay que completar exactamente:

1. número de barras del timeout;
2. unidad monetaria, tamaño de lote y conversión EUR/USD;
3. spread primario para los años sin columna `spread`;
4. slippage primario;
5. comisión por lote;
6. regla de cierre al timeout.

## Aporte del cliente y verificación FundedNext

La comisión indicada por el cliente es **US$5 por lote por lado**. La tabla
oficial de condiciones de FundedNext confirma que la comisión Forex se cobra
`per side`; por tanto, el coste de comisión de un trade completo es **US$10 por
lote** (entrada + salida). La fuente queda registrada en
`fundednext.com/general-rules/cfds/symbols-and-conditions`.

## Escenarios obligatorios

El resultado primario usará un solo escenario congelado. Como control de
robustez se ejecutarán además escenarios de costes mayores, sin elegir después
el que produzca el mejor resultado. El coste histórico de `EXP_C4` (`0,5 pip`
spread, `0,3 pip` slippage y comisión `0`) queda solo como referencia auxiliar;
no es la decisión propuesta ni prueba de costes reales.

## Regla sobre las nueve anomalías

Las nueve filas `DOWNLOAD_SERIALIZATION_ERROR` permanecen intactas. Se excluyen
solo de la construcción de trades mediante la regla ya registrada y se publica
la comparación con/sin anomalías. No se sustituyen por MT5 ni se reparan.

## Gate

El documento no autoriza la ejecución. Hasta completar los seis campos
pendientes, `ECONOMIC_FILL`, `COSTS` y `HORIZON_EXIT` permanecen
`UNKNOWN/BLOCKED`; por tanto, `EXP-PASS-EDGE-INTRADIA-01` sigue en
`DRAFT_BLOCKED / NO EJECUTAR`.
