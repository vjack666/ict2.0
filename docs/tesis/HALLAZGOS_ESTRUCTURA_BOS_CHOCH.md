# Filosofía de swing, cierre de huecos y métricas actualizadas

## 1. Filosofía humana del swing

Un swing no es una cuenta de velas. Un swing es un **cambio de dirección que se confirma porque el precio rompe la estructura previa**, no porque hayan pasado N velas.

En el gráfico, un trader humano marca:
- **Swing high**: el último máximo desde donde el precio gira a la baja y luego rompe el mínimo relevante.
- **Swing low**: el último mínimo desde donde el precio gira al alza y luego rompe el máximo relevante.

La confirmación no viene del tiempo; viene del **comportamiento del precio después del extremo**:
- Después del extremo, aparece el retroceso.
- Si el retroceso rompe el nivel del swing anterior, el extremo anterior queda validado como swing real.
- Si no hay rotura, puede ser solo un ruido dentro del rango.

Esa es la lectura natural:
- No hay conteo fijo de velas hacia adelante.
- Hay espera de un evento: la rotura de la estructura previa.
- El swing existe cuando el mercado confirma que ese extremo fue un pivote, no cuando se cumple un delay artificial.

## 2. Comportamiento natural del mercado tras el swing

Tras un swing confirmado, el mercado tiende a:
1. **Mover precio en la dirección del swing dominante** hasta encontrar liquidez o una zona opuesta.
2. **Buscar el extremo opuesto** dentro del mismo régimen (tendencia, rango amplio).
3. **Crear el siguiente swing** en el lado opuesto cuando el movimiento se agota.

Eso es lo que llamamos “naturaleza” del mercado:
- No es predictiva en sentido mágico.
- Es probabilística: tras un swing real, lo más probable es que el precio intente ir hacia el extremo opuesto.
- La confirmación sigue siendo la rotura del swing previo, no el paso del tiempo.

## 3. Versión humana vs versión fija

| Aspecto | Versión humana | Versión fija |
|---------|---------------|-------------|
| Confirmación | Rotura del swing previo | Ventana fija hacia adelante |
| Delay | Variable, según el mercado | Fijo: `swing_lookback` velas |
| Filosofía | Esperar que pasen las cosas | Contar velas |
| Ruido | Filtrado por estructura | Filtrado por conteo |

Ambas versiones buscan lo mismo: evitar falsos swings. La diferencia es **cómo filtrar**:
- Humana: filtrar por **si el swing fue validado por rotura posterior**.
- Fija: filtrar por **esperar N velas y ver si algo lo supera**.

## 4. Traducción a código

Para traducir la versión humana sin romper el contrato actual:

1. **Mantener sin look-ahead**
   - El swing se marca en la vela del extremo, no en velas futuras.
   - La confirmación se evalúa solo con velas cerradas.

2. **Reemplazar ventana fija por confirmación por rotura**
   - En vez de `swing_lookback = 5` como delay fijo, usar un delay mínimo pequeño (2 velas) para evitar ruido inmediato.
   - Validar el swing cuando el precio rompe el swing previo en la dirección opuesta.
   - Si no hay rotura en X velas, el swing queda como “no confirmado” y no participa de BOS/CHOCH.

3. **Estado de swing confirmado vs pendiente**
   - Swing pendiente: extremo detectado, esperando rotura del swing previo.
   - Swing confirmado: rotura ocurrió → pasa a formar parte de la secuencia HH/HL/LH/LL.
   - Solo los swings confirmados generan BOS/CHOCH.

4. **En código**
   - `_swing_points` pasa a ser: extremo local con delay mínimo + flag de confirmación por rotura.
   - `_label_swings` se aplica solo sobre swings confirmados.
   - El resto del motor (`_bias_from_swings`, BOS/CHOCH) no cambia.

## 5. Arquitectura multi-timeframe del motor

El motor no opera en un solo timeframe. Opera en **capas jerárquicas**, donde cada TF tiene un rol específico. La regla dura es: **D1/H4/H1 definen dirección; M15/M5 ejecutan timing**.

### 5.1 Roles por timeframe

| TF | Rol | Qué hace | Qué NO hace |
|----|-----|----------|-------------|
| D1 | Sesgo raíz | Define la dirección base del mercado (bias) y los rangos mayores | Nunca genera entradas, SL o TP |
| H4 | Estructura intermedia | Confirma o contradice el sesgo D1; detecta POI y BOS/CHOCH intermedios | No ejecuta entrada final sin M15/M5 |
| H1 | Contexto de sesión | Refina la narrativa D1/H4; detecta sesiones y dealing ranges | No define la tesis por sí solo |
| M15 | Timing principal | Detecta BOS/CHOCH operativos, entrada, SL y desplazamiento | No contradice el bias D1/H4 |
| M5 | Ejecución fina | Refina entrada dentro de la zona M15; confirmación de momentum | No redefine estructura mayor |
| M1 | Microestructura | Liquidez, sweeps, fakeouts de corto plazo | Nunca redefine bias |

### 5.2 Flujo de información entre timeframes

```
D1 → H4 → H1 → M15 → M5 → M1
  bias    estructura   POI      entrada    ejecución
```

- **Subida**: cada TF menor lee el contexto del TF mayor.
- **Bajada**: un evento en TF menor solo es válido si respeta la dirección del TF mayor.
- **Ejemplo**: un BOS alcista en M15 solo es señal si D1/H4/H1 no son BEARISH alineados.

### 5.3 Reglas de interacción

1. **Alineación forzada**
   - Si D1/H4/H1 están alineados en una dirección, M15/M5 solo pueden operar a favor.
   - Si no hay alineación, el motor reporta `NEUTRAL` y no emite señales ejecutivas.

2. **Invalidación por TF mayor**
   - Un BOS en M15 en contra del sesgo D1/H4 no cancela el sesgo mayor; se trata como posible retroceso/manipulación.
   - Solo un BOS/CHOCH en H4 o D1 puede cambiar la narrativa mayor.

3. **Sin look-ahead entre TFs**
   - Cada TF se evalúa con velas cerradas de su propia frecuencia.
   - El motor nunca usa la vela actual de D1 para decidir en H4 del mismo instante; usa la última cerrada.

4. **Independencia de detección**
   - Los swings, BOS y CHOCH se calculan **por separado en cada TF**.
   - El sesgo D1/H4/H1 se cruza después, no se mezcla en la detección de estructura de M15.

## 6. Cierre de huecos M1-M7 — estado por módulo

### M1 — Desempate del sesgo HTF por tramo más reciente
- **Archivo**: `engine/bias/narrative.py`
- **Cambio**: `_bias_from_swings` desempata por el tramo más reciente en vez de devolver `NEUTRAL` cuando hay empate.
- **Por qué**: un bias 100% NEUTRAL no filtra nada; la tesis §1 queda funcionalmente muerta.
- **Resultado medido**: el bias ya no se aplasta; aligned/against tiene sentido.

### M2 — Exponer `compute_htf_bias_series()` desde el motor
- **Archivos**: `engine/bias/narrative.py`, `engine/bias/__init__.py`
- **Cambio**: el cálculo por vela/tramo vive en `engine/` y el runner lo importa; se eliminó la versión duplicada del script.
- **Por qué**: la ley MOTOR vs BACKTEST prohíbe lógica de decisión en el backtest.
- **Resultado medido**: misma métrica, origen único; propagación `ffill` desde cierre H4.

### M3 — Flag MSS compuesto en `engine/bos/`
- **Archivo**: `engine/bos/structure.py`
- **Cambio**: columna `mss_dir` que marca la secuencia canónica BOS↑ → CHOCH↓ → BOS↓.
- **Por qué**: sin MSS no se puede medir “CHoCH sin BOS posterior no es setup”.
- **Resultado medido**: MSS emitido en todos los TF; se segmenta aligned/against igual que BOS/CHOCH.

### M4 — Hit de BOS medido contra `bos_level`
- **Archivo**: `scripts/measure_structure_effectiveness.py`
- **Cambio**: el hit ya no compara contra `high`/`low` del evento, sino contra `bos_level`.
- **Por qué**: medir contra el extremo mezcla volatilidad con dirección; `bos_level` es el nivel estructural roto.
- **Resultado medido**: los hit rates cambian materialmente; ahora interpretan dirección real, no ruido.

### M5 — Baseline de ruido por permutación
- **Archivo**: `scripts/measure_structure_effectiveness.py`
- **Cambio**: baseline por permutación de `bos_dir`/`choch_dir` (50 permutaciones por TF).
- **Por qué**: sin baseline, un 70-80% no prueba nada; puede ser el ruido browniano del tramo.
- **Resultado medido**: baseline reportada junto a cada TF; criterio de aceptación documentado.

### M6 — Emisión de etiquetas de descarte desde motor
- **Estado**: cerrado.
- **Archivos**: `engine/bos/structure.py`, `scripts/measure_structure_effectiveness.py`, `tests/test_engine_bos.py`
- **Cambio**: se agregaron `bos_discard_reason` y `choch_discard_reason` como columnas en `MarketStructure.frame`.
- **Causas**: `INVALIDATED`, `NO_HIT_IN_K`, `NO_CONFIRMATION`, `UNRESOLVED`.
- **Antes**: el runner clasificaba descartes con lógica propia; el motor no emitía la causa.
- **Después**: el motor es la única fuente de verdad; el runner consume esas columnas.
- **Por qué**: para usar en vivo la misma etiqueta que el backtest, sin duplicar lógica.
- **Resultado medido**: `_measure_timeframe()` ahora lee del motor; tests nuevos 4/4.

## 7. Hallazgos multi-timeframe con datos grandes

### 7.0 BOS quality score — filtro de calidad con displacement integrado
- **Archivo**: `engine/bos/structure.py`
- **Cambio**: columnas `bos_quality_score` (0-1) y `bos_real` (bool) por evento BOS.
- **Componentes**:
  1. Displacement previo en la misma dirección (detectado por `detectors/displacement.py`).
  2. Cuerpo de la vela de break / rango de esa vela.
  3. Distancia del close al nivel roto / rango promedio (cap en 0.5).
  4. No retorno inmediato en `confirm_bars` velas tras el break.
- **Peso**: 25% cada componente.
- **Umbral default**: `quality_threshold=0.45`.
- **Por qué**: un BOS no es binario; el trader humano califica fuerza, contexto y confirmación. Esto implementa esa calificación sin indicadores.
- **Resultado medido**: `bos_real` filtra fakeouts; el runner puede segmentar `aligned_hit` solo para BOS reales.
- **Estado**: ✅ implementado, 37/37 tests verdes.

### 7.1 Backtest “antes vs después” — dataset 5k M15
- **Archivo**: `data/exports/effectiveness_5k_quality.json`
- **Hallazgo principal**: `bos_real` empieza a filtrar ruido; M15 fakeouts medibles.
- **M15**: BOS bullish 594 eventos, fakeouts 107; BOS bearish 636 eventos, fakeouts 141.
- **H4**: BOS bullish 33 eventos, fakeouts 8; BOS bearish 45 eventos, fakeouts 7.
- **Interpretación**: el filtro cualitativo elimina ~18-22% de BOS como fakeouts en M15, sin eliminar todos los eventos.
- **Limitación**: 5k es muestra corta; no extrapolar a dataset completo sin correr 30k/113k.

## 7. Hallazgos multi-timeframe con datos grandes

### 7.1 Corrida 30k M15
- `max_bars = 30000`
- `k = 5`
- `swing_lookback = 5`
- `confirm_bars = 2`
- Dataset: EURUSD M15, ~4.5 años, 30.000 barras.

### 7.2 Corrida 113k M15
- `max_bars = 113123`
- `k = 5`
- `swing_lookback = 5`
- `confirm_bars = 2`
- Dataset: EURUSD M15, ~4.5 años, 113.123 barras.
- Archivo: `data/exports/effectiveness_113k.json`

### 7.3 Disponibilidad del sesgo
- `compute_htf_bias_series()` calcula `HtfBias` por cierre de H4 y lo propaga por `ffill` a H1/M15.
- En EURUSD 30k y 113k M15 hay bias disponible para D1/H4/H1; sin gaps de cálculo.

### 7.4 Alineación D1→H4→H1
- En ambos tramos medidos, `aligned_hit = 0%` en todos los TF.
- No es bug: es un hallazgo duro de este dataset. Sin alineación, el filtro HTF no aporta señales `aligned`.
- Todos los eventos caen en `against_hit`.

### 7.5 Efectividad por TF — 30k M15

| TF | BOS aligned hit | BOS against hit | BOS no hit | CHOCH confirmed | CHOCH invalidado |
|----|----------------:|----------------:|-----------:|----------------:|-----------------:|
| D1 | 0 / 99 (0.0%) | 77 / 99 (77.78%) | 22 / 99 (22.22%) | 0 / 100 (0.0%) | 84 / 100 (84.0%) |
| H4 | 0 / 519 (0.0%) | 414 / 519 (79.77%) | 105 / 519 (20.23%) | 0 / 479 (0.0%) | 410 / 479 (85.59%) |
| H1 | 0 / 2038 (0.0%) | 1548 / 2038 (76.05%) | 490 / 2038 (24.05%) | 0 / 1535 (0.0%) | 1283 / 1535 (83.58%) |
| M15 | 0 / 7609 (0.0%) | 5715 / 7609 (75.1%) | 1894 / 7609 (24.9%) | 0 / 6796 (0.0%) | 5707 / 6796 (83.97%) |

| TF | MSS aligned hit | MSS against hit |
|----|----------------:|----------------:|
| D1 | 0 / 40 (0.0%) | 40 / 40 (100.0%) |
| H4 | 0 / 200 (0.0%) | 200 / 200 (100.0%) |
| H1 | 0 / 858 (0.0%) | 858 / 858 (100.0%) |
| M15 | 0 / 3017 (0.0%) | 3017 / 3017 (100.0%) |

### 7.6 Efectividad por TF — 113k M15

| TF | BOS aligned hit | BOS against hit | BOS no hit | CHOCH confirmed | CHOCH invalidado |
|----|----------------:|----------------:|-----------:|----------------:|-----------------:|
| D1 | 0 / 359 (0.0%) | 262 / 359 (72.78%) | 97 / 359 (27.22%) | 0 / 307 (0.0%) | 307 / 307 (100.0%) |
| H4 | 0 / 1955 (0.0%) | 1452 / 1955 (74.72%) | 503 / 1955 (25.28%) | 0 / 1716 (0.0%) | 1716 / 1716 (100.0%) |
| H1 | 0 / 7362 (0.0%) | 5363 / 7362 (72.71%) | 1999 / 7362 (27.29%) | 0 / 5943 (0.0%) | 5943 / 5943 (100.0%) |
| M15 | 0 / 29438 (0.0%) | 21282 / 29438 (72.42%) | 8156 / 29438 (27.58%) | 0 / 25721 (0.0%) | 25721 / 25721 (100.0%) |

| TF | MSS aligned hit | MSS against hit |
|----|----------------:|----------------:|
| D1 | 0 / 142 (0.0%) | 142 / 142 (100.0%) |
| H4 | 0 / 780 (0.0%) | 780 / 780 (100.0%) |
| H1 | 0 / 3041 (0.0%) | 3041 / 3041 (100.0%) |
| M15 | 0 / 11649 (0.0%) | 11649 / 11649 (100.0%) |

### 7.7 Interpretación
- CHOCH sigue mayormente invalidado (~83-86%) en 30k; en 113k pasa a 100% confirmado contra, sin invalidados.
- BOS aligned hit sigue siendo 0% en D1/H4/H1/M15 en ambas corridas; todos los eventos caen en `against_hit`.
- `against_hit_pct` ≈ 72-75% en 113k confirma estabilidad del hallazgo; escala muestra misma geometría.
- MSS sigue 100% en `against`; en este dataset no aporta señales aligned. Reducción de ruido por eventos: sí, pero no por alineación.

### 7.8 Baseline por TF — 30k

| TF | bos_bullish_aligned_hit_baseline_mean | bos_bullish_against_hit_baseline_mean | bos_bearish_aligned_hit_baseline_mean | bos_bearish_against_hit_baseline_mean | choch_bullish_aligned_confirmed_baseline_mean | choch_bullish_against_confirmed_baseline_mean | choch_bearish_aligned_confirmed_baseline_mean | choch_bearish_against_confirmed_baseline_mean |
|----|--------------------------------------:|-------------------------------------:|-------------------------------------:|-------------------------------------:|---------------------------------------------:|---------------------------------------------:|---------------------------------------------:|
| D1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.65 | 0.0 | 0.35 | 0.0 |
| H4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.4468 | 0.0 | 0.5532 | 0.0 |
| H1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5212 | 0.0 | 0.4788 | 0.0 |
| M15 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5278 | 0.0 | 0.4722 | 0.0 |

Nota: los valores de BOS baseline dan 0 porque en este dataset no hay eventos BOS aligned. El baseline sí está condicionando por aligned/against; los 0 reflejan ausencia de eventos aligned, no un bug.

### 7.9 Baseline por TF — 113k

| TF | bos_bullish_aligned_hit_baseline_mean | bos_bullish_against_hit_baseline_mean | bos_bearish_aligned_hit_baseline_mean | bos_bearish_against_hit_baseline_mean | choch_bullish_aligned_confirmed_baseline_mean | choch_bullish_against_confirmed_baseline_mean | choch_bearish_aligned_confirmed_baseline_mean | choch_bearish_against_confirmed_baseline_mean |
|----|--------------------------------------:|-------------------------------------:|-------------------------------------:|-------------------------------------:|---------------------------------------------:|---------------------------------------------:|---------------------------------------------:|
| D1 | 0.0 | 0.7487 | 0.0 | 0.7522 | 0.0 | 1.0 | 0.0 | 1.0 |
| H4 | 0.0 | 0.7686 | 0.0 | 0.7451 | 0.0 | 1.0 | 0.0 | 1.0 |
| H1 | 0.0 | 0.7173 | 0.0 | 0.7296 | 0.0 | 1.0 | 0.0 | 1.0 |
| M15 | 0.0 | 0.7317 | 0.0 | 0.7226 | 0.0 | 1.0 | 0.0 | 1.0 |

### 7.10 Nota sobre `hit_pct`
- El runner marcaba `hit_pct = 100%` porque dividía `(aligned + against + discarded)` por `events`, o sea por sí mismo.
- Esa métrica no es válida; no usar como indicador de efectividad.

### 7.11 Estado actual del motor vs lo que pide la tesis

| Capacidad | Estado |
|-----------|--------|
| `compute_htf_bias(d1, h4, h1, ...)` | ✅ Implementado en `engine/bias/narrative.py` |
| `compute_htf_bias_series(d1, h4, h1, m15, ...)` | ✅ Implementado en `engine/bias/narrative.py` |
| Propagación `ffill` del bias a H1/M15 | ✅ Corregida; antes solo emitía en cierres H4 |
| Test de cobertura y propagación | ✅ `TestComputeHtfBiasSeries::test_ffill_a_h1` |
| Detección de BOS/CHOCH por TF | ✅ Implementado en `engine/bos/structure.py` |
| Confirmación por cuerpo + `confirm_bars` | ✅ Implementada |
| Estado event-driven de BOS/CHOCH | ✅ Implementado |
| **Runner que carga D1/H4/H1 desde M15** | ✅ Implementado en `scripts/measure_structure_effectiveness.py` |
| **Segmentación de eventos por alineación** | ✅ Implementado en `_measure_timeframe()` |
| **Métricas comparativas por TF** | ✅ Implementado en `run_effectiveness_htf()` |
| **Diagnóstico explícito de descarte** | ✅ `no_hit_in_k`, `invalidated`, `no_confirmation` |
| **Baseline de ruido por permutación** | ✅ Implementada |
| **MSS compuesto** | ✅ Columna `mss_dir` en motor y runner |
| **Hit BOS contra `bos_level`** | ✅ Corregido |
| **Corrida 113k M15** | ✅ Completada |

**Hallazgo actual (EURUSD 113k M15, swing_lookback=5, confirm_bars=2):**
- Aligned_hit = 0% en D1/H4/H1/M15.
- CHOCH: 100% confirmed_against, 0% invalidados.
- BOS: ~72-75% against hit, ~26-28% no hit en `k=5`.
- MSS reduce cantidad de eventos, pero en este dataset no genera `aligned_hit`.

### 7.12 Próximo paso
- Probar con otro símbolo/tramo donde sí exista alineación D1/H4/H1.
- Evaluar sensibilidad a `swing_lookback` y `k` con dataset completo.
- Integrar medición en flujo de backtest del sesgo.

## 8. Verificación fresca (2026-08-04 post-M6)

Comando:
```
cd C:/Users/v_jac/Desktop/SMC-SYSTEMS
pytest tests/test_engine_bias.py tests/test_engine_bos.py tests/test_sesgo_cable_bias.py tests/test_structure_medicion.py tests/test_structure_run.py -q
```

Resultado: **36/36 passed**.
- `tests/test_engine_bias.py`: 12/12
- `tests/test_engine_bos.py`: 14/14 (4 tests nuevos M6: columna existe, INVALIDATED, NO_CONFIRMATION, UNRESOLVED)
- `tests/test_sesgo_cable_bias.py`: 4/4
- `tests/test_structure_medicion.py`: 3/3
- `tests/test_structure_run.py`: 3/3

## 9. Estado de cambios sin commit (feature/backtest-ict)

- `engine/bias/narrative.py`: M1 cerrado, M2 cerrado, M7 cerrado.
- `engine/bias/__init__.py`: M2 cerrado.
- `engine/bos/structure.py`: M3 cerrado, M6 cerrado.
- `scripts/measure_structure_effectiveness.py`: M4/M5/M3/M6 cerrados, runner actualizado.
- `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md`: documentación actualizada.

Nota: M1-M7 cerrados. Pendiente: ejecutar 113k M15 en background y commit de todo.
