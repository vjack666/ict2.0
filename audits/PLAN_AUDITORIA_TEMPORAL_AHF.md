# PLAN — Auditoría Temporal AHF/MTF

**Estado:** NORMATIVO — estratificada PASS + sandbox multi-ventana PASS (rollback fix validado); full-span 20Y pendiente
**Comando gatillo exacto:** `ejecuta auditoria temporal`
**Dataset:** EURUSD 20Y de `datasets/eurusd_dukascopy_20y/` (2006–2025), con SHA256/metadata del snapshot versionado.
**Auditor canónico:** `audits/codigo/ahf_temporal_navigation_audit.py`
**Driver full-span:** `scripts/tna_20y_parallel.py`
**SDD relacionado:** `docs/planificacion/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`, `docs/contratos/CONTRATO_AHF.md`, `docs/auditoria/AUDITORIA_TEMPORAL_AHF_MTF.md`

## 1. Regla de ejecución

Cuando Hermes reciba exactamente **`ejecuta auditoria temporal`**, debe ejecutar la auditoría sobre el snapshot EURUSD 20Y versionado. No debe sustituir el dataset, reducir el período ni usar una muestra aleatoria como resultado final. Una muestra estratificada puede utilizarse como evidencia preliminar y debe etiquetarse como tal.

La auditoría es pre-backtest y **no es un backtest**: no produce PnL, no autoriza entradas y no cambia reglas para obtener PASS.

## 2. Secuencia obligatoria

1. Actualizar/clonar `main` y verificar el commit del dataset.
2. Verificar `SHA256SUMS` y metadata del dataset 20Y.
3. Cargar H1/H4/D1 disponibles; usar M15/M5 solo si el snapshot requerido existe y está versionado.
4. Ejecutar AHF sobre una línea temporal de decisión ordenada.
5. Registrar trace de estados y transiciones.
6. Ejecutar `audits/codigo/ahf_temporal_navigation_audit.py`.
7. Validar PIT/look-ahead y timestamps `as_of(t)`.
8. Generar JSON/Markdown dentro de la carpeta canónica de reportes.
9. Si falla un gate, diagnosticar/corregir/testear y volver a ejecutar sin cambiar el criterio después de observar el resultado.
10. Actualizar `.hermes-index.md` y `.hermes-worklog/` con resultado, commit, dataset/hash y cobertura.

## 3. Qué debe medir

### Duración / latencia

- barras hasta `D1_LOCKED`, `H4_LOCKED`, `WAIT_LTF`, `SETUP_READY`;
- duración total;
- mediana, p90, p95 y máximo por estado/transición.

### Navegación

- transiciones;
- timeframe activo;
- profundidad máxima;
- revisitas;
- avance/espera/retroceso;
- estados atascados;
- cadenas que no llegan a `SETUP_READY`.

### Backtracking / invalidación

- invalidaciones por capa;
- causa y estado;
- rollback;
- reconfirmación;
- ciclos de ida-vuelta;
- recuperación vs abandono.

### Magnitud FVG / OB — descriptiva

Medir tamaño y excursión posterior solo como descripción geométrica/dinámica, no como TP/SL, entrada, R o PnL.

Ventanas mínimas:

```text
+1, +3, +6, +12, +24, +48 barras
```

Para EURUSD usar `pip_size=0.0001` salvo metadata explícita. La excursión comienza estrictamente después de `birth_bar`.

### Integridad temporal

- `as_of(t)` correcto;
- ningún contexto confirmado con datos posteriores;
- ningún estado reescrito retrospectivamente;
- monotonicidad del trace;
- invalidaciones con causa/timestamp verificables;
- excursiones solo con barras posteriores al nacimiento/confirmación.

## 4. Definición operativa del paseo

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

Invalidaciones pueden devolver a una capa superior. El contexto confirmado permanece congelado hasta invalidación explícita.

## 5. Evidencia ya obtenida

1. **Muestra 2017 (Hermes 1762746):** `reports/audits/AUDITORIA_TEMPORAL_AHF_RESULT.json` — `PASS_TRACE_INTEGRITY`, 750 steps, 501 transiciones, 193 invalidaciones. Estratificada; `rollback_depth` estaba roto (siempre 0).

2. **Sandbox multi-ventana (Grok 2026-08-20):** `reports/audits/ahf_temporal_navigation_SANDBOX.json` — 3 ventanas (2017/2020/2024), 170 steps, 51 invalidaciones, **rollback_depth max = 2.0**. Overall sandbox **PASS**. Valida el fix de instrumentación (`state_to_tf`). Runner: `scripts/tna_sandbox_runner.py`.

Ninguna de las dos declara cobertura full-span de 20 años. La corrida definitiva sigue siendo `scripts/tna_audit_runner.py` sobre las 124k barras H1.

## 6. Criterios de PASS full-span

La auditoría full-span puede marcar PASS solo si:

- dataset 20Y/hash verificables;
- trace reproducible en el snapshot completo;
- cero PIT/look-ahead;
- transiciones con evento/estado/timestamp/parent state;
- rollback con causa;
- estados unfinished contabilizados;
- FVG/OB descriptivos reproducibles;
- reporte versionado;
- cobertura full-span explícita.

**PASS de esta auditoría no significa edge ni rentabilidad.**

## 7. Ubicación de resultados

Convención actual del repositorio:

```text
reports/audits/
  AUDITORIA_TEMPORAL_AHF_RESULT.json
  mtf_seq_funnel.json
```

Si se genera una nueva corrida full-span, crear un nombre/versionado nuevo o un artifact claramente asociado al commit; no sobrescribir silenciosamente evidencia histórica.

## 8. Gobernanza

- No convertir esta auditoría en backtest.
- No utilizar PnL para aprobarla.
- No relajar thresholds después de mirar resultados.
- Cada ejecución debe dejar commit, dataset/hash, timestamp y worklog.
- Actualizar `.hermes-index.md` inmediatamente.
- No reutilizar excursiones positivas como TP implícito.

## 9. Entrega

El resultado debe indicar siempre:

```text
AUDITORIA_TEMPORAL_AHF_20Y
Dataset: <commit/hash>
Cobertura: ESTRATIFICADA | FULL_SPAN
Estado: PASS | FAIL | BLOCKED
Cadenas/traces auditados: <n>
SETUP_READY: <n>
Invalidaciones: <n>
Revisitas: <n>
Violaciones PIT: <n>
Estados bloqueados: <n>
Reporte: <path>
JSON: <path>
```

La cobertura es parte del resultado y nunca debe ocultarse detrás de un `PASS` genérico.
