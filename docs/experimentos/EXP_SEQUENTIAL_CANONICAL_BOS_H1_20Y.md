# EXP — Cadenas secuenciales con BOS canónico (H1 20Y)

**Fecha:** 2026-08-18  
**Motor:** `engine/sequential_events.py` · `structure_mode=canonical_bos`  
**BOS:** `detectors.bos.detect_bos` (cruce único de nivel, anti-flood)  
**Artefacto:** `reports/audits/experiments/sequential/sequential_canonical_bos_H1_20Y.json`

---

## Comparación embudo: lite vs canónico

| Métrica | BOS-lite | **BOS canónico** |
| --------- | ---------: | -----------------: |
| Cadenas totales | 1.460 | 1.460 |
| Depth 1 (POOL) | 767 | 767 |
| Depth 2 (+SWEEP) | 575 | 575 |
| Depth 3 (+DISP) | 52 | **94** |
| Depth 4 (+STRUCTURE) | 60 | **21** |
| COMPLETE (7 etapas) | 5 | **3** |

El BOS canónico **endurece** el paso STRUCTURE (60 → 21). Más displacement llega a intentar structure, pero menos lo supera.

---

## Expectancy (end>0 / mean move) +24 H1

| Bucket | mode | n | end>0 +24 | mean end +24 |
| -------- | ------ | --: | ----------: | -------------: |
| COMPLETE @ RETEST | canonical | 3 | 66.7 % | +0.0060 |
| COMPLETE @ RETEST | lite | 5 | 80.0 % | +0.0043 |
| DEPTH≥4 @ BOS | canonical | 24 | 54.2 % | −0.0002 |
| DEPTH≥4 @ BOS | lite | 66 | 62.1 % | +0.0023 |
| DEPTH≥5 @ OB | canonical | 3 | 0.0 % | −0.0038 |
| DEPTH≥6 @ FVG | canonical | 3 | 66.7 % | +0.0045 |
| **BASELINE FVG** | — | 500 | **49.6 %** | +0.0004 |

---

## Lectura

1. **BOS canónico no resuelve el problema de n:** COMPLETE sigue en 3–5.
2. El bucket más “grande” usable es **DEPTH≥4 @ BOS** (n=24 canónico / 66 lite). Tasas ~54–62 % — **aún en zona de ruido** frente a baseline ~50 %.
3. Entrada en OB (depth≥5) sale mala en esta muestra mínima.
4. **Caveat de integridad:** `detect_bos` usa swings `center=True` (geometría de pivote con velas futuras). El *break* en sí usa `shift(1)`. Para auditoría estricta point-in-time habría que portar pivotes solo causales al detector BOS.

---

## Política

```text
BOS canónico en la secuencia  =  mejor definición de STRUCTURE
BOS canónico                  ≠  edge demostrado (n bajo)
```

Siguiente: pivotes BOS 100 % causales, o CHOCH canónico, o outcome con stop fijo sobre DEPTH≥4.
