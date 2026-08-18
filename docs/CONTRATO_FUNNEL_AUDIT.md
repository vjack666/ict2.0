# Contrato — Funnel Audit ICT FVG/OB

**Estado:** NORMATIVO
**Gate:** A7

## Objetivo

El Funnel Audit debe ser una auditoría determinista, point-in-time y reproducible de la población de eventos del motor.

## Entradas obligatorias

1. dataset identificado por versión/hash;
2. commit de código;
3. configuración congelada;
4. contrato de objetos vigente;
5. detectores canónicos;
6. lineage vigente.

## Salidas obligatorias

- reporte de funnel por etapa;
- rechazo por razón;
- conteos por dirección/TF;
- duplicados;
- huérfanos;
- violaciones temporales;
- checksum del reporte;
- estado `PASS/WARN/FAIL`.

## Invariantes

### Causalidad
Ninguna etapa puede leer una barra posterior a su `observation_time`.

### Prefijo
La ejecución sobre `bars[:t]` y la ejecución sobre el dataset completo deben producir el mismo resultado para eventos cuya observación sea `<= t`.

### Idempotencia
Ejecutar dos veces el mismo snapshot produce el mismo reporte.

### Unicidad
No se contabiliza el mismo objeto lógico más de una vez.

### Lineage
Todo candidato aceptado tiene lineage válido o una razón explícita de por qué no requiere padre.

### Determinismo
No se permite dependencia de orden de iteración, reloj del sistema, aleatoriedad no sembrada o datos externos no versionados.

## Razones de rechazo mínimas

```text
INVALID_DATA
DUPLICATE_EVENT
TEMPORAL_VIOLATION
MISSING_PARENT
INVALID_PARENT
CONTRACT_VIOLATION
INVALID_GEOMETRY
INVALID_DIRECTION
UNCONFIRMED_EVENT
LEGACY_AMBIGUITY
OUTSIDE_AUDIT_WINDOW
```

## Gate

### PASS
- cero violaciones temporales;
- cero corrupción crítica;
- cero duplicados lógicos no explicados;
- cero lineage inválido en candidatos;
- reproducción idéntica;
- todas las reducciones del funnel explicables.

### WARN
Sólo para anomalías descriptivas no críticas y siempre con explicación registrada.

### FAIL
Cualquier fuga futura, duplicación no explicada, lineage inválido, no determinismo o corrupción de datos.

## Prohibiciones

- No cambiar umbrales para conseguir un funnel "bonito".
- No eliminar outliers sin una regla definida antes de la ejecución.
- No usar PnL para seleccionar eventos.
- No optimizar parámetros durante la auditoría.
- No incorporar OTE/Fibonacci.

## Cierre

Al terminar el Gate A7 Hermes debe actualizar:

- `docs/SDD_FUNNEL_AUDIT.md`;
- `docs/PLAN_PRE_BACKTEST_AUDIT_STACK.md` si cambia el alcance;
- `docs/SDD_FVG_OB_ARCHITECTURE_MAP.md`;
- `.hermes-index.md`;
- `.hermes-worklog/<timestamp>_FUNNEL_AUDIT.md`.

Sin esa sincronización, A7 no se considera cerrado.
