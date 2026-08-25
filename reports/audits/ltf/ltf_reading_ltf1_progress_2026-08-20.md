# LTF Reading — avance de LTF-1

**Estado:** EN PROGRESO — no es `PASS` de LTF-1 ni de LTF Reading.
**Perfil:** `DAILY_D1_H4_H1_M15_READING` (`D1 → H4 → H1 → M15`)
**Política:** `OBSERVE_ONLY_NO_ORDER`

## Cambios verificados

- `DailyMotorConfig` exige `profile_id`, `htf`, `itf`, `context_tf` y `exec_tf` explícitos.
- El snapshot expone `asof_times_by_tf`, `navigation`, `context`, `sequence`, `ltf` y `lineage_refs`.
- La salida se normaliza a tipos JSON y ordena referencias para determinismo.
- FVG/OB solo se promueven desde `MarketObject` canónico por `canonical_zones`.
- Los marcadores legacy del DataFrame se conservan como diagnóstico y no promueven zona/retest.
- El retest requiere `tradable_time <= first_touch_time <= decision_time` y `touch_count >= 1`.
- Una contradicción estructural explícita de LTF no puede cambiar el `direction_hint` heredado.
- El brief consume el mismo snapshot y no contiene una FSM o detector paralelo.
- No existe salida de orden; `entry_authorized` permanece `false`.

## Pruebas ejecutadas

```text
py -m pytest tests/test_daily_motor.py -q
9 passed

py -m pytest -q
61 passed, 1 warning
```

Las pruebas cubren futuro añadido solo a D1, H4 y M15, futuro añadido a todos
los timeframes, serialización, determinismo, autoridad LTF, zona canónica y
retest. La advertencia existente proviene de `engine/bias/narrative.py` y no
es un fallo de LTF.

## Pendiente para cerrar el gate

- Conectar los detectores canónicos y la Sequence productiva al caller diario.
- Consumir Context State/AHF real, incluyendo rollback auditable.
- Ejecutar validación histórica D1→H4→H1→M15 con invariancia por prefijo.
- Publicar cobertura histórica de `NO_LTF_DATA`, `WAIT_*` y `OBSERVABLE_SETUP`.
