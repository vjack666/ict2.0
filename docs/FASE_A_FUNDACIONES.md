# FASE A — FUNDACIONES DEL MOTOR ICT

**Fecha:** 2026-08-17  
**Fase:** A — Fundaciones / contratos base  
**Estado:** `IN_PROGRESS / GATE_PENDING`  
**Objetivo:** dejar una base ejecutable, verificable y temporalmente segura antes de continuar con FVG/OB.

## 1. Alcance

Fase A no implementa nuevos detectores de estrategia. Su responsabilidad es asegurar las condiciones mínimas sobre las que FVG/OB podrá construirse sin introducir deuda estructural.

### A1 — Ejecución reproducible

- El repositorio debe poder instalar sus dependencias en GitHub Actions.
- La suite debe arrancar sin depender de archivos inexistentes.
- Las dependencias deben declararse explícitamente.

**Corrección aplicada:** se añadió `requirements.txt` con `pytest` y `pytest-cov`, eliminando el fallo de `actions/setup-python` que buscaba `requirements.txt`/`pyproject.toml` y no encontraba ninguno.

### A2 — Contrato base de `MarketObject`

El objeto canónico debe impedir estados estructuralmente imposibles sin decidir todavía la semántica específica de FVG/OB.

Invariantes ahora verificadas:

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

La representación de un objeto no debe permitir registrar una confirmación, disponibilidad o evento de lifecycle anterior a su propia aparición temporal.

Los tests contractuales cubren actualmente los casos de orden temporal, primer toque e invalidación.

### A4 — Serialización estable

`MarketObject.to_dict()` / `from_dict()` debe conservar los campos del contrato sin perder identidad, estado, temporalidad ni lineage directo.

El round-trip está cubierto por test.

### A5 — CI como evidencia

El workflow `.github/workflows/hermes-tests.yml` ya ejecuta `pytest`. La ausencia de `requirements.txt` era un fallo de infraestructura, no del motor. La corrección permite que el runner instale dependencias de forma reproducible.

## 2. Gate A

El Gate A **no se declara PASS todavía**. Debe existir una ejecución real de GitHub Actions posterior a este commit con:

```text
setup-python       PASS
install deps       PASS
pytest             PASS
```

Además, no se deben introducir cambios de estrategia FVG/OB durante esta validación.

## 3. Criterio de salida

Fase A pasa únicamente si:

1. CI instala dependencias sin error;
2. `pytest` termina con código 0;
3. todos los tests de contrato base pasan;
4. no se relajan invariantes para conseguir verde;
5. el índice Hermes y el worklog reflejan la evidencia real.

Si falla cualquier punto: `FAIL`, corregir y repetir.

## 4. Fuera de alcance de A

- detector canónico FVG;
- detector canónico OB;
- Breaker/BPR como detectores;
- scoring de setups;
- aprendizaje de FVG/OB;
- validación M5;
- OTE/Fibonacci.

M5 permanece diferido y H1/H4/D1 pueden utilizarse para validaciones estructurales posteriores, sin presentarlas como validación M5.

## 5. Próximo paso

Ejecutar el workflow de tests. Sólo con evidencia verde se cierra A y se habilita formalmente la Fase B.
