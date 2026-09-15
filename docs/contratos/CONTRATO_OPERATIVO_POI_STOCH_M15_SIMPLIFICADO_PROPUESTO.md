# CONTRATO OPERATIVO PROPUESTO — Estrategia Simplificada POI+Stoch M15
## Como ruta alternativa a Fase 2B

**Estado:** BORRADOR DE DECISIÓN — no aplica hasta autorización expresiva de Rubén.

> Documento de cierre de misión. No activa órdenes, no reinicia servicio, no modifica código ni contratos vigentes. Resuelve la pregunta de qué querríamos operar si la decisión es "operar simplificado" en lugar de "esperar Fase 2B".

---

## 1. Declaración de lo que NO se usa

Esta ruta alternativa **no** regenera ni reactiva:

- **Ningún probability fabricada.** No hay campo `probability`, no hay `score_to_probability()`, no hay umbral de 70% como gate de entrada. La evaluación de entrada es binaria: el cruce estocástico M15 vigente + POI elegible en proximidad + sesión + gates de riesgo.
- **Ningún confirmed legacy del productor mecánico.** `validate_snapshot()` con `confirmed=true` queda fuera de este contrato operativo. Este documento define una autoridad de entrada distinta: POI elegible + cruce M15, no la cadena de confirmación H4/H1→M15 sweep→displacement→BOS/CHoCH→FVG/OB→retest.
- **Ningún layout del productor Fase 2A ni Fase 2B.** No se utiliza `mechanical_signal_assessment`, no se escribe `latest_snapshot.json` desde este contrato, no se publica dirección/probabilidad/confirmación con el formato del productor mecánico.
- **Ninguna evidencia económica.** Este documento es el contrato operativo de la estrategia, no el certificado D5/CRO que autorizaría explotación.

---

## 2. Autoridad de entrada propuesta

La estrategia simplificada **sí** usa:

- **POI elegible** definido por `CONTRATO_POI_STOCH_M15_V2.md`, secciones 2.1 a 2.5:
  - Tipo: `ObjectType.FVG` o `ObjectType.ORDER_BLOCK`.
  - Temporalidad de origen: `D1`, `H4` o `H1` (los POI-TFs acordados; M15 permanece como TF de ejecución, no como POI primario).
  - Estado: `ObjectState.ACTIVE` o `ObjectState.PARTIALLY_MITIGATED`.
  - Símbolo, geometría válida (`zone_high`/`zone_low` finitos, `zone_high >= zone_low`), y nacimiento antes del `decision_time` (`tradable_time <= decision_time`).
  - Dirección: `+1` o `-1`.
  - **Sin condición de `Role.POI`** — el motor operativo publica con `Role.REFINEMENT` y eso es aceptable para este contrato.
- **Cruce estocástico M15 vigente** definido por `CONTRATO_POI_STOCH_M15_V2.md`, secciones 5 a 8:
  - Parámetros: 14, 3, 3; mínimo 20 velas; `closed_m15_candles(symbol, count=80)`.
  - Cruce alcista: `previous_k <= 20, previous_d <= 20, previous_k <= previous_d, k > d` → `CROSS_UP_FROM_OVERSOLD`.
  - Cruce bajista: `previous_k >= 80, previous_d >= 80, previous_k >= previous_d, k < d` → `CROSS_DOWN_FROM_OVERBOUGHT`.
  - Vigencia: relación K/D mantenida en la vela más reciente, no vencido por 3 velas sin nuevo cruce válido, verificable con datos disponibles, `cross_id` no consumido.
  - Coincidencia de dirección: el cruce debe ser coherente con la POI seleccionada.
- **Sesión** como gate independiente:
  - La sesión Londres/NY vigente (definida por el servicio actual) permanece como condición de ejecución, igual que en `_readiness()` actual.
  - POI+Stoch no reemplaza el gate de sesión; lo complementa.
- **Gates de riesgo del servicio:**
  - `execution_enabled` como habilitación global del loop.
  - `snapshot` edad/antigüedad como gate de datos frescos.
  - `cycle` activo en misma dirección como bloqueo de repetición.
  - Cualquier gate adicional que la decisión de operación exija (SL/TP, volumen, exposure) se añade como capa nueva, no como parte de este contrato de entrada.

---

## 3. Definición de `readiness.ready` para este contrato

El campo `readiness.ready` debe representar **esta autoridad real** cuando se opte por la ruta simplificada, no una mezcla de gates legacy con gates nuevos.

### 3.1. Forma propuesta

```
ready = execution_enabled
      AND snapshot_fresh
      AND session_london_ny_open
      AND poi_stoch_result is not None
      AND poi_stoch_result.status == "ENTRY_VALID"
      AND (gates_extras TODO cumplidos)
```

### 3.2. Invariantes que `ready` debe conservar

- **No mezcla legacy/nueva:** cuando el resultado POI+Stoch existe, `ready` se deriva de él, no de `direction + probability + confirmed + m15_confirmation` del layout legacy.
- **No implica confirmación mecánica:** `ready` puede ser `true` con `poi_stoch_result.status == "ENTRY_VALID"` incluso cuando el productor mecánico diría `NO_SIGNAL` o `BLOCKED` (porque este contrato no usa su cadena de confirmación).
- **Fail-closed por defecto:** si no hay `poi_stoch_result` o el status no es `ENTRY_VALID`, `ready` es `false`.

### 3.3. Qué NO significa `ready`

- `ready=true` no significa que el productor mecánico haya certificado la entrada.
- `ready=true` no significa que exista probabilidad calibrada ni que haya pasar por los gates de Fase 2B.
- `ready=true` no significa que la sesión se haya abierto en el momento exacto del cruce; la sesión es un gate independiente que debe estar abierto al `decision_time`.

---

## 4. Invariante global `can_trade=false`

El contrato propuesto **no** habilita trading por sí mismo.

- `can_trade=false` permanece como invariante global del servicio y de la terminal hasta que:
  1. Este contrato sea adoptado explícitamente por decisión de Rubén,
  2. Se complete la verificación técnica del estado resultante,
  3. Se complete la auditoría D5/CRO correspondiente si la ruta se promociona.
- Adoptar el contrato no equivale a autorizar operación. Equivale a definir **cuál sería la autoridad de entrada** si la operación se autoriza luego.
- El bot permanece en modo lectura/observación con `Armar bot` habilitado pero el loop sin ejecución real.

---

## 5. Frontera con Fase 2B

Este documento es **alternativa**, no suplemento de Fase 2B.

- Si la decisión es esperar Fase 2B, este documento queda como referencia de la estrategia simplificada y como evidencia de que existe un contrato operativo distinto al del productor mecánico, pendiente de decisión.
- Si la decisión es operar simplificado, este documento propone la frontera: la estrategia simplificada no espera la certificación de Fase 2B, pero tampoco hereda sus gates ni su autoridad. Es un contrato nuevo, con su propio campo de autoridad.
- Los dos caminos conservan invariantes comunes: `engine/` no importa `backtest/`, `can_trade=false` salvo autorización, y ninguna prueba envía órdenes reales ni DEMO sin contrato explícito.

---

## 6. Estado del contrato para esta misión

- **Definido:** autoridad de entrada (POI elegible + cruce M15 vigente + sesión + gates de riesgo), declaración de lo no usado (probability fabricada, confirmed legacy), invariante `can_trade=false`.
- **Pendiente de decisión:** adopción del contrato por Rubén, definición de gates extra de operación, verificación de estado resultante, auditoría si se promociona.
- **No aplica en esta misión:** evaluación histórica, backtest, calibración, dictamen D5/CRO.

---

## 7. Archivos de referencia

- `docs/contratos/CONTRATO_POI_STOCH_M15_V2.md` — autoridad canónica de la estrategia simplificada (cruce, POI, vigencia, cross_id, campos de salida, algoritmo de evaluación).
- `docs/tesis/SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md` — contrato del productor mecánico (Fase 1, 2A, 2B), contra el que esta ruta alternativa NO se apoya.
- `.hermes-worklog/2026-09-15_MT5_EPOCH_CLOCK_POI_STOCH_M15.md` — worklog de la misión (este documento).
- `.hermes/plans/2026-09-14_POI_STOCH_M15_SIMPLIFICATION.md` — plan de la misión.

---

> Documento generado como parte del cierre de MC-20260914-083000-poi-stoch-m15. No es contrato vigente hasta decisión de operar.
