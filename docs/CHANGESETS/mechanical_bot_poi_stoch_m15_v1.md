# Bitácora de Cambios — Adaptación Bot Mecánico a POI + Estocástico M15

> MC-20260914-083000-poi-stoch-m15 · Tarea 6 · Departamento D2 Ingeniería  
> Plan: `.hermes/plans/2026-09-14_POI_STOCH_M15_SIMPLIFICATION.md`  
> Fecha: 2026-09-14

## Qué se hizo

Se adaptaron `mechanical_bot/service.py` y `mechanical_bot/core.py` para que el bot mecánico
consuma la evaluación POI + estocástico M15 (`engine/poi_stoch_evaluator.py`) en lugar del
sistema completo de 9 gates, respetando el contrato `docs/contratos/CONTRATO_POI_STOCH_M15_V1.md`.

**Modificaciones mínimas, no reescritura.**

---

## Archivos modificados

### `mechanical_bot/service.py`

**1. `_readiness()` — Nuevo gate POI+Stoch (líneas 286-309)**

El método ahora comprueba si hay un `poi_stoch_result` disponible. Si existe, reemplaza los
gates `direction`, `probability` y `m15_confirmation` por un único gate `poi_stoch_m15` que
consume el resultado de `evaluate_poi_stoch_m15()` y considera `ENTRY_VALID` como condición
de entrada.

Los gates de `execution_enabled`, `snapshot` y `session` se mantienen como controles
operativos independientes (no se tocan).

El gate de probabilidad (`min_probability=0.70`) ya no es un bloqueo rígido del bot: pasa a
ser un parámetro configurable del evaluador (ver `PoiStochConfig` en `engine/poi_stoch_evaluator.py`).

Cuando NO hay `poi_stoch_result`, el método cae al path legacy de 9 gates para mantener
compatibilidad con el sistema completo.

**Cambios en el flujo de gates:**

```
ANTES (6 gates): execution_enabled → snapshot → direction → probability(≥0.70) → m15_confirmation → session
DESPUÉS:
  - Con POI+Stoch:  execution_enabled → snapshot → session → poi_stoch_m15(ENTRY_VALID)
  - Sin POI+Stoch:  execution_enabled → snapshot → direction → probability → m15_confirmation → session (legacy intacto)
```

**2. `tick()` — Lógica de entrada adaptada (líneas 468-509)**

El bloque `else` (línea 468) ahora usa `evaluate_poi_stoch_m15()` cuando el snapshot canónico
disponible tiene `object_projection` con POI elegibles y hay lectura estocástica M15.

Correcciones aplicadas:
- Campo correcto: `raw.get("object_projection", [])` en lugar de `raw.get("market_objects", [])`
  (el campo `market_objects` no existe en el snapshot canónico; solo `object_projection` lo tiene).
- Extracción de dirección robusta: maneja tanto objetos como dicts deserializados para
  `poi_selected["direction"]`.

La lógica de `manual_entry()` permanece intacta para compatibilidad.

### `mechanical_bot/core.py`

**1. `validate_poi_stoch_entry()` — Nueva función (líneas 108-144)**

Función de validación que acepta el resultado de `evaluate_poi_stoch_m15()` y devuelve
`"BUY"` o `"SELL"` si el status es `ENTRY_VALID`.

A diferencia de `validate_snapshot()` que exige `confirmed=true`, esta verificación usa el
cruce estocástico M15 como confirmación — tal como define el contrato simplificado.

Maneja tanto objetos como dicts (serializados) para `poi_selected`.

**2. `validate_snapshot()` — Preservado intacto**

No se eliminó. Mantiene la validación `confirmed=true` para compatibilidad con el sistema
completo. Es usado por el path legacy en `_readiness()` y por `tick()` en el bloque de
ejecución deshabilitada.

---

## Qué NO se cambió

- `validate_snapshot()` — conservado 100% para compatibilidad con sistema completo.
- `manual_entry()` — conservado intacto en `service.py` y `core.py`.
- `mechanical_bot/mt5_adapter.py` — no tocado.
- `engine/poi_stoch_evaluator.py` — creado por Tarea 5, no modificado aquí.
- `docs/contratos/CONTRATO_POI_STOCH_M15_V1.md` — congelado, no tocado.

---

## Decisión de diseño: por qué ENTRY_VALID como condición única

El contrato define la siguiente jerarquía de status:

```
NO_ELIGIBLE_POI_NEAR_PRICE (no POI en zona → no entrar)
  ↓ requiere POI cerca
NO_CROSS / INSUFFICIENT_CANDLES / CROSS_EXPIRED / CYCLE_ACTIVE_SAME_DIRECTION (condiciones de espera)
  ↓ requiere cruce válido y no vencido
ENTRY_VALID (entrada autorizada)
```

El gate `poi_stoch_m15` en `_readiness()` usa `ENTRY_VALID` como condición de entrada porque
es el único status que representa "todas las condiciones cumplidas". Los otros status son
condiciones de espera o error, no entrada.

Esto reemplaza la combinación antigua de:
- `direction` (dirección del snapshot)
- `probability >= 0.70` (umbral rígido)
- `confirmed=true` (confirmación del snapshot)
- `m15_cross compatible` (cruce estocástico M15)

Por un único gate que integra todo: POI cerca + dirección operable + cruce M15 válido y no
vencido + sin ciclo activo en misma dirección.

---

## Decisión de diseño: min_probability como parámetro del evaluador

En el sistema completo, el bot bloqueaba si `probability < 0.70`. Con la estrategia
simplificada, la "probabilidad" ya no es un campo del snapshot sino el resultado integral de
la evaluación POI+Stoch.

El parámetro `min_probability` existe en `BotConfig` por compatibilidad, pero ya no es un
bloqueo en `_readiness()`. En su lugar, `PoiStochConfig` (Protocol en el evaluador) acepta
parámetros de estilo y tolerancia que controlan la evaluación. Si en el futuro se requiere
un umbral de probabilidad mínimo para la estrategia simplificada, se añade como campo de
`PoiStochConfig`, no como bloqueo rígido en el bot.

---

## Riesgos identificados

1. **Compatibilidad con sistema completo**: El path legacy en `_readiness()` se ejecuta
   cuando no hay `poi_stoch_result`. Si en producción el snapshot canónico nunca incluye
   `object_projection` con POI elegibles, el bot cae al path legacy automáticamente. Esto
   es seguro por diseño (fallback implícito).

2. ** Campo `object_projection`**: El evaluador consume MarketObjects desde
   `object_projection` del snapshot. Si el productor canónico no publica ese campo, el
   evaluador no se ejecuta en `analyze()` ni en `tick()`. No hay error — simplemente no
   hay evaluación POI+Stoch disponible ese tick.

3. **Serialización/deserialización**: `poi_selected` puede ser un dict (cuando viene de
   JSON) u objeto. `validate_poi_stoch_entry()` y `tick()` manejan ambos casos. Sin
   embargo, si en el futuro el evaluador retorna tipos personalizados, hay que extender
   la lógica de extracción.

4. **Desfase entre `analyze()` y `tick()`**: Ambos métodos calculan `poi_stoch_result`
   independientemente. Si entre un `analyze()` y un `tick()` cambia el snapshot o las
   velas M15, los resultados pueden diferir. Esto es aceptable porque `tick()` es la
   autoridad de entrada real; `analyze()` es solo dashboard.

---

## Pruebas ejecutadas

- `test_mechanical_bot_core.py`: 24/24 PASSED
- `test_mechanical_bot_service.py`: 53/54 PASSED (1 fallo preexistente unrelated:
  `test_disarm_waits_for_running_tick_and_blocks_later_execution` — race condition de
  threading en el test, no relacionado con los cambios)
- Test de integración manual: `evaluate_poi_stoch_m15()` + `validate_poi_stoch_entry()`
  con objetos y dicts: OK
- Importación y ejecución de `MechanicalBotService.analyze()` con mock: OK

---

## Siguiente acción

Tarea 7 del plan: validar la integración en entorno de test con datos reales de velas M15
y POI canónicas, comparando resultados del evaluador vs. sistema completo en casos de
borde (cruce vencido, POI fuera de zona, ciclo activo, etc.).

---

## Evidencia de cambios (diff resumido)

```
mechanical_bot/service.py:
  + Nuevas líneas 286-309: bloque POI+Stoch en _readiness()
  + Línea 478: campo object_projection en tick()
  + Líneas 486-495: extracción robusta de dirección del poi_selected

mechanical_bot/core.py:
  + Líneas 108-144: validate_poi_stoch_entry() (nueva función)
  + Línea 139-143: manejo de dict y objeto para poi_selected.direction
```

---

*Bitácora generada por D2 Ingeniería como parte de MC-20260914-083000-poi-stoch-m15.*
