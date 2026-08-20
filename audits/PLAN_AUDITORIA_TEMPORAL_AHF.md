# PLAN — Auditoría Temporal AHF/MTF

**Estado:** NORMATIVO — lista para ejecución bajo comando explícito
**Comando gatillo exacto:** `ejecuta auditoria temporal`
**Dataset:** EURUSD 20Y de `datasets/eurusd_dukascopy_20y/` (2006–2025), con SHA256/metadata del snapshot versionado.
**Auditor canónico:** `audits/codigo/ahf_temporal_navigation_audit.py`
**SDD relacionado:** `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`, `docs/contratos/CONTRATO_AHF.md`, `docs/auditoria/AUDITORIA_TEMPORAL_AHF_MTF.md`

## 1. Regla de ejecución

Cuando Hermes reciba exactamente **`ejecuta auditoria temporal`**, debe ejecutar esta auditoría sobre el snapshot EURUSD 20Y versionado. No debe sustituir el dataset por otro, reducir el período ni usar una muestra aleatoria como resultado final.

La auditoría es pre-backtest y **no es un backtest**: no produce PnL, no autoriza entradas y no cambia reglas para obtener PASS.

## 2. Secuencia obligatoria

1. Actualizar/clonar `main` y verificar el commit del dataset.
2. Verificar `SHA256SUMS` y metadata del dataset 20Y.
3. Cargar H1/H4/D1 disponibles; usar M15/M5 sólo si el snapshot requerido existe y está versionado.
4. Ejecutar AHF sobre una línea temporal de decisión ordenada.
5. Registrar el trace completo de estados y transiciones.
6. Ejecutar `audits/codigo/ahf_temporal_navigation_audit.py`.
7. Validar que no haya look-ahead ni timestamps fuera de `as_of(t)`.
8. Generar el reporte JSON y Markdown dentro de `audits/`.
9. Si falla un gate, diagnosticar/corregir/testear y volver a ejecutar la auditoría hasta obtener un resultado válido; nunca cambiar el criterio después de observar el resultado.
10. Actualizar `.hermes-index.md` y `.hermes-worklog/` con el resultado, commit, dataset/hash y estado PASS/FAIL/BLOCKED.

## 3. Qué debe medir

### Duración / latencia

- barras desde inicio de evaluación hasta `D1_LOCKED`;
- barras desde `D1_LOCKED` hasta `H4_LOCKED`;
- barras desde `H4_LOCKED` hasta `WAIT_LTF`;
- barras desde `WAIT_LTF` hasta `SETUP_READY`;
- duración total del recorrido;
- distribución por estado (mediana, p90, p95, máximo).

### Navegación

- número de transiciones;
- timeframe activo por transición;
- profundidad máxima alcanzada;
- número de revisitas por timeframe;
- ratio avance / espera / retroceso;
- estados que permanecen demasiado tiempo sin resolver;
- casos que nunca llegan a `SETUP_READY`.

### Backtracking / invalidación

- número de invalidaciones D1/H4/H1;
- estado donde ocurrió la invalidación;
- cuántas velas/decisiones retrocedió;
- profundidad del rollback (número de capas);
- velas hasta reconfirmación;
- número de ciclos de ida-vuelta por cadena;
- porcentaje de cadenas que se recuperan tras rollback;
- porcentaje que termina bloqueada/abandonada.

### Magnitud FVG / OB — descriptiva, no TP/SL

Para cada FVG y OB observado en un trace y para cada timeframe disponible:

- tamaño de la zona en pips (`size_pips`);
- precio de referencia y regla de referencia;
- máxima distancia posterior a favor (`max_favorable_pips`);
- máxima distancia posterior en contra (`max_adverse_pips`);
- desplazamiento firmado al cierre de la ventana (`end_move_pips`);
- barras hasta máximo favorable/adverso, cuando sea posible reconstruirlas sin futuro.

Ventanas mínimas:

```text
+1, +3, +6, +12, +24, +48 barras
```

Para EURUSD, usar `pip_size=0.0001` salvo metadata explícita del símbolo. El movimiento debe empezar estrictamente **después** de `birth_bar`; nunca se usan barras anteriores para medir excursión posterior.

Estas métricas sirven para describir la geometría y dinámica del objeto. **No son TP, SL, entrada, R, expectancy ni PnL.**

### Integridad temporal

- `as_of(t)` correcto por timeframe;
- ningún contexto confirmado con datos posteriores a `t`;
- ningún estado reescrito retrospectivamente;
- coherencia `transition_time <= decision_time`;
- monotonicidad temporal del trace;
- eventos de invalidación con causa y timestamp verificables;
- excursiones FVG/OB calculadas sólo con barras posteriores al nacimiento/confirmación del objeto.

## 4. Definición operativa del "paseo"

El AHF se interpreta como una máquina de estados jerárquica dirigida por eventos:

```text
WAIT_D1
  ↓ condición D1
D1_LOCKED
  ↓
WAIT_H4
  ↓ condición H4
H4_LOCKED
  ↓
WAIT_H1
  ↓ condición H1
WAIT_LTF
  ↓ confirmación LTF
SETUP_READY
```

Una invalidación puede devolver el proceso a una capa superior:

```text
H1_INVALIDATED → WAIT_H1
H4_INVALIDATED → WAIT_H4
D1_INVALIDATED → WAIT_D1
```

El contexto confirmado de una capa permanece congelado hasta su invalidación explícita. La auditoría debe verificar esa regla.

## 5. Criterios de PASS

La auditoría temporal puede marcar **PASS** sólo si:

- el dataset 20Y y su hash son verificables;
- el trace completo es reproducible;
- no existen violaciones PIT/look-ahead;
- todas las transiciones tienen evento, estado, timestamp y parent state;
- todo rollback tiene causa explícita;
- las duraciones y retrocesos son calculables sin ambigüedad;
- los estados bloqueados/unfinished quedan contabilizados;
- FVG/OB tienen tamaño en pips reproducible;
- las excursiones posteriores respetan estrictamente `birth_bar + 1` en adelante;
- las métricas descriptivas no se convierten en reglas TP/SL/entrada;
- el reporte se genera y queda versionado.

**PASS de esta auditoría no significa edge ni rentabilidad.** Significa que la navegación temporal del AHF y la medición descriptiva de FVG/OB son observables, reproducibles y temporalmente íntegras.

## 6. Ubicación obligatoria de resultados

Los resultados deben quedar en la carpeta canónica de auditorías:

```text
audits/
  PLAN_AUDITORIA_TEMPORAL_AHF.md
  AUDITORIA_TEMPORAL_AHF_20Y.md
  reports/
    AUDITORIA_TEMPORAL_AHF_20Y.json
```

Si el repositorio ya usa otra subestructura canónica para artefactos JSON de auditoría, mantener la convención existente y enlazarla desde este plan.

## 7. Gobernanza

- No convertir esta auditoría en un backtest.
- No utilizar PnL para aprobarla.
- No usar M5 ausente como excusa para saltar H1/H4/D1.
- No relajar thresholds después de mirar resultados.
- Cada ejecución debe dejar commit, dataset/hash, timestamp y worklog.
- El resultado debe actualizar `.hermes-index.md` inmediatamente.
- No reutilizar una distancia positiva medida después de FVG/OB como TP implícito.

## 8. Entrega final esperada

Al completar `ejecuta auditoria temporal`, Hermes debe devolver un resumen con:

```text
AUDITORIA_TEMPORAL_AHF_20Y
Dataset: <commit/hash>
Estado: PASS | FAIL | BLOCKED
Cadenas auditadas: <n>
SETUP_READY: <n>
Mediana hasta SETUP_READY: <n> velas
P95 hasta SETUP_READY: <n>
Invalidaciones: <n>
Rollback medio: <n> velas
Rollback P95: <n>
Revisitas MTF: <n>
Violaciones PIT: <n>
Estados bloqueados: <n>
FVG size mediana/p90 por TF: <...>
OB size mediana/p90 por TF: <...>
FVG favorable/adverso por ventana: <...>
OB favorable/adverso por ventana: <...>
Reporte: audits/AUDITORIA_TEMPORAL_AHF_20Y.md
JSON: audits/reports/AUDITORIA_TEMPORAL_AHF_20Y.json
```

**Regla:** si el comando se solicita de nuevo, se ejecuta otra vez sobre el snapshot actual de `main` y se conserva el nuevo resultado como nueva evidencia; no se sobreescribe silenciosamente la historia anterior.
