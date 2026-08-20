# Auditoría Funnel — EURUSD H1 / H4 / D1

**Fecha:** 2026-08-18  
**Autor:** Hermes (ICT SYSTEM)  
**Dataset:** ejtraderLabs/historical-data (CSV → parquet normalizado)  
**Rango:** 2012-11 → 2022-03  
**IA desactivada:** `CHOCH_IA_DISABLE=1` (score geométrico puro)

---

## 1. Objetivo

Medir el embudo de detección de estructura ICT sobre data gratuita H1/H4/D1:

```
OHLC → SWING → BOS raw → BOS unique → CHOCH unique → CHOCH real → class (premium/useful/noise)
```

Y auditar la integridad de la capa de datos antes de cualquier afirmación de edge.

---

## 2. Capa DATA — Integridad

| TF | Filas | Nulls | Duplicados | Bad OHLC | Orden temporal | Gaps grandes* | Parquet |
|----|------:|------:|-----------:|---------:|:--------------:|--------------:|--------:|
| H1 | 57.600 | 0 | 0 | 0 | ✓ | ~495 (fines de semana) | 1.6 MB |
| H4 | 14.400 | 0 | 0 | 0 | ✓ | ~493 | 573 KB |
| D1 | 2.400 | 0 | 0 | 0 | ✓ | 0 | 110 KB |

\* Gaps de fin de semana / feriados en forex son normales; no se rellenan.

**Normalización aplicada:** precios originales venían ×100.000 → divididos a unidades EURUSD reales.  
**Schema:** `time, open, high, low, close`  
**Veredicto DATA:** **PASS**

Archivos:
```
data/raw/EURUSD/EURUSD_H1.parquet
data/raw/EURUSD/EURUSD_H4.parquet
data/raw/EURUSD/EURUSD_D1.parquet
data/metadata/EURUSD_H1_H4_D1.json
```

---

## 3. Funnel de detección — Resultados

| TF | Bars | Swing | BOS unique | CHOCH unique | CHOCH real | premium | noise | score medio |
|----|-----:|------:|-----------:|-------------:|-----------:|--------:|------:|------------:|
| **H1** | 57.600 | 7.088 | 382 | 562 | **10** | 10 | 552 | 35.1 |
| **H4** | 14.400 | 1.771 | 100 | 139 | **2** | 2 | 137 | 33.7 |
| **D1** | 2.400 | 285 | 15 | 24 | **0** | 0 | 24 | 25.8 |

### Tasas de conversión (H1)

| Etapa | Tasa | Lectura |
|-------|------|---------|
| bars → swing | 12.3 % | ~1 de cada 8 barras es pivote |
| swing → BOS unique | 5.4 % | pocos swings generan BOS de tesis |
| BOS unique → CHOCH unique | ~147 % | un BOS puede alimentar varios CHOCH candidatos |
| CHOCH unique → real | **1.8 %** | la gran mayoría no cumple after_bos + nivel pivote |
| real → premium | 100 % (n=10) | con score geométrico, los real llegan a premium |

### Configuración de la corrida

- `SwingTool(lookback=5)`
- `BOSTool` + `apply_validation` + `filter_bos_thesis(confirm_bars=2)`
- Solo eventos con `is_unique=True`
- `mark_choch_quality` con `htf_frames={}` (sin sesgo HTF inyectado)
- Umbrales de clase: premium ≥ 90, useful ≥ 70, noise < 70
- Componente IA = 0 (desactivado a propósito)

Artefacto: `data/metadata/funnel_audit_H1_H4_D1.json`

---

## 4. Interpretación (hechos, no narrativa)

1. **El funnel es coherente con el dominio documentado.**  
   En M5 histórico se midió ~90–93 % reclaim post-CHOCH. Aquí, en H1/H4, solo 1.4–1.8 % de CHOCH unique son `choch_real`. No es un bug de código: es la rareza del patrón “giro real tras BOS opuesto + nivel pivote intacto”.

2. **Sin HTF el score se deprime.**  
   `htf_frames={}` fuerza contexto neutral → menos puntos de alineación. En producción, `build_daily_bias` debería levantar algunos scores de setups alineados con D1/H4.

3. **Premium es escaso pero no cero en H1/H4.**  
   10 premium en ~10 años de H1 ≈ 1 por año. Útil para lectura estructural, insuficiente como fuente única de señales de alta frecuencia.

4. **D1 no produjo CHOCH real.**  
   Con lookback actual y ~10 años, la estructura diaria es demasiado gruesa. Esperable; no invalidar el detector por esto.

5. **Data gratuita es suficiente para desarrollo H1/H4.**  
   M5 sigue DEFERRED (inventario oficial). No afirmar validación M5 con esta data.

---

## 5. Limitaciones de esta auditoría

| Limitación | Impacto |
|------------|---------|
| Sin HTF bias inyectado | Scores más bajos de lo posible en prod |
| Sin modelo IA | El 15 % de IA no se midió aquí |
| Data hasta 2022-03 | No cubre 2023–2026 |
| Solo EURUSD | No multi-par |
| Lookback swing fijo = 5 | En D1 puede ser insuficiente (TF_LOOKBACK adaptativo existe en código reciente) |
| No se midió FVG/OB | Fuera de alcance de este funnel (plan activo FVG/OB es paralelo) |

---

## 6. Guía de recomendaciones

### Prioridad ALTA (hacer ya)

| # | Recomendación | Por qué | Cómo |
|---|---------------|---------|------|
| R1 | **Inyectar HTF bias y re-medir funnel** | Sin D1/H4 el score geométrico subestima premium | Correr de nuevo `mark_choch_quality` con `htf_frames` desde `detect_trend` H4/D1 |
| R2 | **No usar CHOCH real como señal de alta frecuencia** | 1–2 % de conversión; ~1 premium/año en H1 | Tratar CHOCH real/premium como **filtro de contexto**, no como trigger |
| R3 | **Mantener M5 DEFERRED** | Esta data no es M5; afirmar edge M5 sería falso | Seguir `DATA_INVENTARIO_ACTUALIZADO.md` |
| R4 | **No promocionar el 15 % IA hasta walk-forward estricto del GBM** | ROC 0.798 es split aleatorio; B3 dio PR-AUC 0.07–0.31 OOS | Ejecutar `b3_walkforward_strict.py` cuando haya features H1 generadas |

### Prioridad MEDIA

| # | Recomendación | Por qué |
|---|---------------|---------|
| R5 | Generar dataset CHOCH H1/H4 con esta data y correr walk-forward estricto | Cierra el círculo evidencia OOS en TF disponibles |
| R6 | Ablation de `score_n` en el modelo | Medir cuánto del ROC in-sample dependía de la feature más correlacionada |
| R7 | Usar lookback adaptativo por TF (`TF_LOOKBACK`) en D1 | lookback=5 en D1 es microestructura; puede explicar 0 CHOCH real |
| R8 | Documentar hash SHA256 de cada parquet en metadata | Trazabilidad reproducible |

### Prioridad BAJA / posterior

| # | Recomendación |
|---|---------------|
| R9 | Incorporar multi-par (GBPUSD, USDJPY, XAUUSD) cuando haya fuente estable |
| R10 | Cuando haya M5 estable (MT5 local o Dukascopy), repetir funnel completo y comparar tasas vs H1 |
| R11 | Shadow-mode del nature head (B4) antes de cablear al bias del motor |

---

## 7. Decisiones que NO se toman con esta auditoría

- No se cambia el umbral premium (≥ 90).
- No se desactiva el componente IA en producción (solo se marca como baja confianza OOS).
- No se modifica el detector CHOCH.
- No se declara PASS del plan FVG/OB (es track paralelo).

---

## 8. Archivos de evidencia

```
AUDITORIA_FUNNEL_EURUSD_H1_H4_D1.md          ← este documento
data/metadata/EURUSD_H1_H4_D1.json                ← integridad OHLC
data/metadata/funnel_audit_H1_H4_D1.json          ← conteos del funnel
data/raw/EURUSD/EURUSD_{H1,H4,D1}.parquet         ← data (gitignored)
.hermes-worklog/2026-08-18_1435_AUDITORIA_FUNNEL.md
```

---

## 9. Gate de esta auditoría

| Criterio | Resultado |
|----------|-----------|
| Data íntegra y ordenada | **PASS** |
| Funnel ejecutable sin crash | **PASS** |
| Conteos reproducibles | **PASS** |
| Edge OOS demostrado | **NO MEDIDO** (fuera de alcance) |
| Listo para desarrollo FVG/OB en H1 | **SÍ** (con las restricciones de arriba) |

**Veredicto global:** `PASS CON RESTRICCIONES`  
Continuar desarrollo estructural en H1/H4. No afirmar edge de CHOCH como señal primaria.
