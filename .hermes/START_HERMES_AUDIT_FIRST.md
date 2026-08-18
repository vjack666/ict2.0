# START HERMES — Protocolo obligatorio de arranque

## Regla 0

**Hermes NO inicia ninguna fase del plan hasta ejecutar primero el subsistema de auditorías.**

Punto de entrada:

```bash
python start_hermes.py
```

El script llama primero a:

```bash
python -m audits.codigo.bootstrap
```

## Loop obligatorio

```text
START HERMES
   ↓
AUDIT FIRST
   ↓
¿resultado aceptable?
   ├─ NO → leer findings → corregir → tests → actualizar SDD/index/worklog → AUDIT FIRST
   └─ SÍ → habilitar fase siguiente
```

La ejecución se repite hasta un máximo configurable (`HERMES_AUDIT_MAX_ITER`, por defecto 5). Si el agente Hermes está disponible localmente, `HERMES_FIX_COMMAND` debe apuntar al comando que procesa los findings y modifica el repositorio.

Ejemplo:

```bash
export HERMES_FIX_COMMAND='python -m hermes_agent --fix-from-audit'
python start_hermes.py
```

## Umbral medianamente bueno

Hermes puede continuar sólo si se cumplen simultáneamente:

- cero hallazgos `CRITICAL`;
- cero hallazgos `HIGH`;
- cero violaciones de look-ahead;
- A0 pasa;
- A7 pasa cuando corresponda a su fase;
- `audit_score >= 0.80`.

Este umbral **no equivale a Gate final PASS**. Sólo significa que el estado es suficientemente sano para continuar la investigación bajo el Gate específico de la fase.

## Prohibiciones

- No saltarse auditorías porque un test de fase esté verde.
- No relajar reglas para mejorar artificialmente el score.
- No ejecutar backtest de performance cuando el plan indique `BACKTEST BLOCKED`.
- No declarar PASS sólo porque el proceso compiló.
- No borrar findings históricos; deben quedar en la bitácora.

## Documentación obligatoria por ciclo

Al terminar cada intento:

1. `.hermes-worklog/<timestamp>_AUDIT*.md`;
2. `.hermes-index.md`;
3. SDD/documentación aplicable;
4. resultado de tests/CI;
5. decisión `PASS/WARN/FAIL` y siguiente acción.

## Ubicación del código

Todo código ejecutable del subsistema de auditorías vive bajo:

```text
/audits/codigo/
```

No se permite crear una segunda implementación ejecutable fuera de esa carpeta.
