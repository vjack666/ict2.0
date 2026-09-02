# Decisión pendiente — parámetros económicos del baseline Edge intradía

**Fecha:** 2026-09-02  
**Estado:** `PROXY_PILOT_FROZEN`  
**Experimento:** `EXP-PASS-EDGE-INTRADIA-01`  
**Alcance:** investigación local; sin IA, órdenes ni promoción

## Datos MT5 locales incorporados

La instancia configurada del terminal es
`C:\Program Files\FundedNext MT5 Terminal\terminal64.exe`, pero la sesión
observada estaba conectada a `MetaQuotes-Demo`, no a un servidor FundedNext.
El cliente autoriza usar esta cuenta demo para los primeros pasos técnicos y de
investigación local, sin abrir todavía una cuenta FundedNext. Por eso estos
valores se incorporan como **proxy local observado**, no como condiciones
certificadas del broker:

| Campo | Valor observado |
|---|---|
| Símbolo | EURUSD |
| Contract size | 100.000 |
| Dígitos | 5 |
| Tick size/value | 0,00001 / US$1 |
| Spread instantáneo | 1 punto = 0,1 pip |
| Swap long/short | -0,7 / -1,0 |
| Volumen mínimo/paso | 0,01 / 0,01 |

El spread es una observación puntual y no representa toda la distribución
histórica. La comisión de US$5 por lado proviene de las condiciones oficiales
del modelo FundedNext elegido y no de esta sesión MetaQuotes-Demo; ambas
fuentes no se mezclan sin declararlo.

La cuenta demo no permite inferir cumplimiento de reglas FundedNext, costes
reales, ejecución real ni `can_trade=true`. Todo resultado de esta fase se
etiquetará `PROXY_PILOT`.

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
| Coste primario | proxy local observado de 0,1 pip cuando no exista spread histórico; reportarlo separadamente |
| Slippage | `0,3 pip` fijo, separado del spread |
| Comisión | `US$5 por lote por lado` = `US$10` por trade completo |

## Decisiones que todavía requieren congelación

La tesis fija la mecánica ICT, pero no fija los valores económicos universales.
Antes de correr el baseline hay que completar exactamente:

1. número de barras del timeout: **12 velas M15**;
2. unidad monetaria, tamaño de lote y conversión EUR/USD;
3. spread primario para los años sin columna `spread`: **1 pip**;
4. slippage primario: **0,3 pip**;
5. comisión por lote: **US$5 por lado**;
6. regla de cierre al timeout: **cierre al precio de la última barra del horizonte**.

Con autorización del cliente, estos parámetros quedan congelados para el
`PROXY_PILOT`. No certifican condiciones FundedNext ni sustituyen una
distribución histórica de slippage; el baseline debe publicar estas
limitaciones y conservar una sensibilidad con costes mayores.

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
