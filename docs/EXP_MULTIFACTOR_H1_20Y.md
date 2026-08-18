# EXP — Co-ocurrencia multi-factor en torno a FVG (H1 20Y)

**Fecha:** 2026-08-18  
**Estado:** **CONGELADO — EVIDENCIA EXPLORATORIA**  
**Resultado:** no se encontró edge operativo con co-ocurrencia simple de factores  
**Artefacto:** `reports/audits/multifactor_structure_disp_liq_htf_H1.json`

---

## Pregunta

¿Añadir displacement, estructura, HTF (proxy EMA) y/o liquidez (proxy sweep) **en la misma ventana** que un FVG mejora el outcome a +24 barras H1 respecto al FVG solo?

---

## Diseño (proxies — no módulos finales del motor)

| Factor | Proxy usado | Limitación |
|--------|-------------|------------|
| Displacement | `tools.detect_displacement` en 3 velas del FVG | OK geométrico |
| Estructura | Swings causales HH/HL vs LH/LL (lb=5) | No BOS/CHOCH canónico |
| HTF | EMA20/50 H4+D1, `merge_asof` backward | **No es bias ICT** |
| Liquidez | Barrido simple de extremo 20 barras | **No EQH/EQL formal** |
| Causal OB→FVG | `FVG_OB_CAUSAL` strict | Lineage, no señal |

Universo: todos los FVG H1 detectables · n≈22.468 · horizonte +24 · EURUSD Dukascopy 2006–2025.

---

## Tabla de métricas (congelada)

| Bucket | n | end>0 | MFE>MAE | med_end |
|--------|--:|------:|--------:|--------:|
| ALL_FVG | 22.468 | 50.0 % | 50.6 % | ~0 |
| CAUSAL_ONLY | 677 | 50.5 % | 51.4 % | ~0 |
| DISPLACEMENT_IN_WINDOW | 5.768 | 50.7 % | 52.4 % | ~0 |
| NO_DISPLACEMENT | 16.700 | 49.8 % | 49.9 % | ~0 |
| STRUCTURE_ALIGNED | 3.926 | 50.8 % | 49.7 % | ~0 |
| STRUCTURE_AGAINST | 2.717 | 49.2 % | 50.7 % | ≤0 |
| H4_ALIGNED | 6.690 | 49.2 % | 48.9 % | ≤0 |
| D1_ALIGNED | 6.546 | 49.0 % | 50.2 % | ≤0 |
| **H4_AND_D1_ALIGNED** | 2.143 | **46.9 %** | 48.0 % | ≤0 |
| HTF_NOT_ALIGNED | 11.375 | 50.5 % | 51.3 % | ~0 |
| LIQ_SWEEP_RECENT | 5.735 | 49.3 % | 50.5 % | ≤0 |
| NO_LIQ_SWEEP | 16.733 | 50.3 % | 50.6 % | ~0 |
| DISP+STRUCT | 1.108 | 51.0 % | 50.0 % | ~0 |
| DISP+HTF_BOTH | 507 | 47.3 % | 49.5 % | ≤0 |
| **STRUCT+HTF_BOTH** | 400 | **43.2 %** | 43.8 % | ≤0 |
| DISP+STRUCT+HTF | 99 | 46.5 % | 46.5 % | ≤0 |
| FULL_STACK / +LIQ | ≤3 | n insuficiente | — | — |

---

## Hallazgos

```text
FVG
 ↓
+ displacement
 ↓
+ estructura
 ↓
+ HTF (EMA)
 ↓
+ liquidez (proxy)
        ≈ 50%
```

- **No** apareció un bucket con edge operativo claro (p. ej. end>0 estable ≫ 55 % con n decente).
- Algunas combinaciones **empeoraron** (H4+D1 46.9 %; STRUCT+HTF 43.2 %; DISP+STRUCT+HTF 46.5 %).
- Eso **no** prueba que “HTF sea malo en ICT”: prueba que **EMA20/50 no es una representación suficiente del bias ICT**. No sacar conclusiones fuertes de ese proxy.

---

## Cadena de falsaciones / neutralidades (contexto)

| Experimento | Resultado aproximado |
|-------------|----------------------|
| FVG solo | ~50 % |
| OB→FVG causal | ~50 % |
| FVG + displacement | ~50 % |
| FVG + estructura | ~50 % |
| FVG + HTF proxy | ~50 % o peor |
| Co-ocurrencia multi-flag | ~50 % |

**Conclusión correcta:**  
*Los objetos aislados y la simple suma de flags no contienen suficiente información predictiva.*

**Conclusión incorrecta a evitar:**  
*“ICT no funciona.”*

---

## Política derivada

```text
Co-ocurrencia de flags  ≠  setup
FVG_OB_CAUSAL           =  lineage / contexto
HTF EMA                 ≠  bias ICT canónico
```

No añadir “cinco filtros más” del mismo tipo.

---

## Siguiente experimento (no ejecutado aquí)

Pasar de **co-ocurrencia** a **secuencia de eventos**:

```text
LIQUIDITY (EQH/EQL)
  → SWEEP
  → DISPLACEMENT
  → BOS / CHOCH
  → OB
  → FVG
  → RETEST
        → outcome
```

Usar módulos reales del motor (`liquidity_*`, structure/BOS/CHOCH, displacement, OB/FVG, retest), no proxies EMA/sweep simplificados.

Ese es el experimento que puede enseñar algo nuevo; este EXP queda **congelado** como evidencia de que la suma de flags no basta.

---

## Gate de este documento

| Criterio | Resultado |
|----------|-----------|
| Evidencia numérica versionada | Sí (JSON) |
| Hipótesis “flags co-ocurrentes ⇒ edge” | **No soportada** |
| Proxies finales del motor | No — intencionalmente exploratorios |
| Acción | Congelar; no iterar más flags; construir secuencia |
