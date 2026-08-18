# EXP — ¿FVG_OB_CAUSAL predice mejor outcome que el resto de FVG?

**Fecha:** 2026-08-18  
**Estado:** **HIPÓTESIS FALSADA**  
**TF / data:** EURUSD H1 · Dukascopy 2006–2025 (20Y)  
**Artefacto numérico:** `reports/audits/fvg_ob_forward_strict_vs_rest_H1.json`

---

## Hipótesis

> Los FVG con relación causal estricta OB→FVG (`FVG_OB_CAUSAL`) tienen **mejor comportamiento futuro** que los FVG sin esa relación.

“Mejor” = mayor tasa de movimiento neto a favor, MFE>MAE, o menor mitigación adversa en horizontes +6…+48 barras H1 tras la confirmación del FVG.

---

## Diseño

| Grupo | n (FVG únicos) | Definición |
|-------|---------------:|------------|
| STRICT_CAUSAL | 678 | `relate_fvg_ob(..., causal_mode="strict")` |
| SYMMETRIC_ONLY | 1.501 | Solape geométrico sin orden OB→FVG |
| NO_RELATION | 20.296 | Sin pareja OB |
| ALL_FVG | 22.475 | Control global |

Métricas post-confirmación: `end>0`, `MFE>MAE`, mitigación del gap, continuación, medianas MFE/MAE/end.

---

## Resultado

A +24 barras H1 (representativo):

| Grupo | end>0 | MFE>MAE |
|-------|------:|--------:|
| STRICT_CAUSAL | **50.4 %** | 51.3 % |
| NO_RELATION | 49.6 % | 50.4 % |
| ALL_FVG | 50.0 % | 50.6 % |

En +6…+48 el strict oscila ~46–52 %, indistinguible del azar y del control.  
Medianas de movimiento neto ≈ 0 en todos los grupos.

**Veredicto experimental: hipótesis FALSADA.**

---

## Qué sí quedó en pie

```text
OB → FVG
    ↓
✅ relación causal reproducible
    ↓
✅ lineage correcto (parent=OB, child=FVG)
    ↓
❌ edge predictivo aislado
```

| Afirmación | Estado |
|------------|--------|
| `FVG_OB_CAUSAL` = contexto / lineage | **VIGENTE** |
| `FVG_OB_CAUSAL` = señal de entrada | **RECHAZADA** |
| Trabajo de relación “falló” | **No** — la auditoría cumplió su función |

---

## Implicación de plan

No convertir confluencia visual en entrada automática.

Siguiente capa de estudio (setup candidato, no relación sola):

```text
estructura + displacement + liquidity + HTF + OB + FVG + timing
        ↓
   setup candidato
        ↓
     outcome
```

La relación OB→FVG **sola no alcanza** para expectancy.

---

## Gate de este experimento

| Criterio | Resultado |
|----------|-----------|
| Medición OOS histórica 20Y | Hecha |
| Control vs NO_RELATION / ALL | Hecha |
| Hipótesis predictiva aislada | **FALSADA** |
| Uso permitido de `FVG_OB_CAUSAL` | Contexto / lineage únicamente |
