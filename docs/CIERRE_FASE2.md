# Cierre de FASE 2 — veredicto de completitud

## Qué se ejecutó (plan: "hacer ejecutar el motor real dentro de ICT SYSTEM")

- FASE 2a: migración de autoridad documental (SPEC + rulebooks + wyckoff).
- FASE 2b: motor rescatado bajo demanda (engine/, ict_backtest/, detectors/)
  y arrancado: build_features(OHLC) -> 52 columnas -> AgentOrchestrator -> 25 agent_*.
- FASE 2c: mapeo agente<->motor; integrada premium_discount_zone
  (engine.dealing_range) en build_features.

## Límite honesto del plan

El plan era "primera ejecución real del motor dentro de ICT SYSTEM".
ESE objetivo está CUMPLIDO: el motor corre, emite 52 columnas del contrato
ICT, y la capa de consenso de ICT SYSTEM las consume y produce 25 columnas agent_*.

## Las 8 columnas pendientes NO se cierran aquí (y por qué)

Son límite de DATOS / ARQUITECTURA, no paso del plan omitido:

| Columna que analysis/* lee | Por qué no se cierra en FASE 2 |
| --- | --- |
| macro_direction | requiere TF mayores D1/H4/H1; build_features opera sobre 1 frame. Necesita rediseño MTF (compute_htf_bias_series en engine/bias/narrative.py ya existe, pero build_features debe recibir frames MTF). |
| volume_confirmed | engine/_volume.volume_confirm requiere columna `volume`; los datos disponibles (data/ml) son features ya procesadas SIN columna volume. Sin datos de volumen, no se produce. |
| market_regime | no hay módulo en el motor que emita régimen de mercado como columna de barra. |
| volatility_regime | idem; volatilidad hoy es solo `atr` (rango). |
| trend_confidence | el motor emite `trend` (dirección) pero no un score de confianza. |
| range_compression | no hay módulo que la emita. |
| divergence | no hay módulo que la emita (requeriría comparar precio vs oscilador). |
| directional_efficiency | no hay módulo que la emita. |

## Decisión (Regla de Oro / sin inventar)

NO se fabrican estas columnas. Hacerlo sería violar el contrato de datos
(SPEC) y la regla de no inventar evidencia. Mientras tanto los agentes
devuelven NEUTRAL/None en esas vías (usaron .get() defensivo, por eso
FASE 2b no crasheó). Son PENDIENTES de diseño explícito, documentadas,
no hueco silencioso.

## Veredicto

FASE 2 = COMPLETA en lo ejecutable. El sistema ICT SYSTEM tiene motor +
capa de consenso integrados y corriendo. Cobertura de columnas: 22/30
(~73%). Las 8 restantes requieren (a) datos con `volume` y (b) rediseño
MTF de build_features, fuera del alcance de "primera ejecución".
