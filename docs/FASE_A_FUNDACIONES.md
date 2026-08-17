# FASE A — FUNDACIONES DEL MOTOR ICT

**Fecha:** 2026-08-17  
**Fase:** A — Fundaciones / contratos base  
**Estado:** `PASS — GATE A CERRADO`  
**Objetivo:** dejar una base ejecutable, verificable y temporalmente segura antes de continuar con FVG/OB.

## 1. Alcance

Fase A no implementa nuevos detectores de estrategia. Su responsabilidad es asegurar las condiciones mínimas sobre las que FVG/OB podrá construirse sin introducir deuda estructural.

### A1 — Ejecución reproducible

- El repositorio instala sus dependencias en GitHub Actions.
- La suite arranca sin depender de archivos inexistentes.
- Las dependencias están declaradas explícitamente en `requirements.txt`.

### A2 — Contrato base de `MarketObject`

El objeto canónico impide estados estructuralmente imposibles sin decidir todavía la semántica específica de FVG/OB.

Invariantes verificadas:

- `origin_tf` obligatorio;
- POI solamente en D1/H4/H1;
- `direction ∈ {-1, 0, 1}`;
- `zone_high >= zone_low`;
- `touch_count >= 0`;
- `age_bars >= 0`;
- `candidate <= confirmation <= tradable` cuando existen;
- `tradable` requiere `confirmation`;
- `first_touch_bar >= tradable_bar` cuando ambos existen;
- `invalidated_bar >= candidate_bar` cuando ambos existen.

Estas reglas son de integridad temporal/estructural y no sustituyen las reglas ICT de detección.

### A3 — Anti-look-ahead estructural

La representación de un objeto no permite registrar una confirmación, disponibilidad o evento de lifecycle anterior a su propia aparición temporal.

### A4 — Serialización estable

`MarketObject.to_dict()` / `from_dict()` conserva identidad, estado, temporalidad y lineage directo.

### A5 — CI como evidencia

GitHub Actions ejecuta la suite sobre Python 3.11 con dependencias fijadas. El workflow fuerza explícitamente el root del repositorio en `PYTHONPATH` y verifica la importación de `engine` antes de ejecutar pytest.

## 2. Gate A — RESULTADO

**PASS**

Ejecución real:

- **Workflow:** `Hermes Tests`
- **Run:** `#26`
- **Run ID:** `32081912747`
- **Commit:** `dacf7b221d22d1549b6aa687fbf2421da6430212`
- **Merge ref probado por GitHub:** `dc0e9948ce44c8c25f6a8084364389e37b7abd95`
- `setup-python`: PASS
- instalación de dependencias: PASS
- verificación `import engine`: PASS
- `pytest`: PASS
- resultado: **8 passed in 0.02s**

No se relajaron invariantes para obtener el resultado verde.

## 3. Criterio de salida

Todos los criterios de salida fueron satisfechos:

1. CI instala dependencias sin error — PASS.
2. `pytest` termina con código 0 — PASS.
3. Tests de contrato base pasan — PASS.
4. No se relajaron invariantes para conseguir verde — PASS.
5. Índice Hermes y worklog se actualizan con evidencia — PASS.

## 4. Fuera de alcance de A

- detector canónico FVG;
- detector canónico OB;
- Breaker/BPR como detectores;
- scoring de setups;
- aprendizaje de FVG/OB;
- validación M5;
- OTE/Fibonacci.

M5 permanece diferido y H1/H4/D1 pueden utilizarse para validaciones estructurales posteriores, sin presentarlas como validación M5.

## 5. Decisión

**Fase A cerrada con PASS.** La Fase B queda formalmente habilitada para comenzar según el plan y sus gates propios.
