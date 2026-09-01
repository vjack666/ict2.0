# SPEC TESIS FORMAL — Enmienda v1.1: eliminación de OTE

**Fecha:** 2026-08-17  
**Estado:** VIGENTE  
**Autoridad:** Enmienda del contrato firmado `docs/ict/SPEC_TESIS_FORMAL.md`  
**Alcance:** eliminar OTE como criterio, filtro, refinamiento o fuente de score del sistema operativo.

## 1. Decisión

A partir de esta enmienda, **OTE (Optimal Trade Entry) queda fuera del modelo operativo de `ict2.0`**.

El documento firmado v1.0 se conserva como trazabilidad histórica. Esta enmienda **sobrescribe únicamente las referencias operativas a OTE** cuando exista conflicto con este documento.

## 2. Núcleo ICT operativo

El sistema debe priorizar la cadena:

`HTF bias → liquidez → sweep → displacement → BOS/CHOCH → FVG/OB → retorno a zona → entry → SL estructural → TP en liquidez`

Los PD Arrays principales para la entrada son:

- **FVG (Fair Value Gap)**
- **Order Block (OB)**
- **BPR / combinaciones OB+FVG**, cuando corresponda al modelo existente

Premium/Discount y EQ pueden mantenerse como **contexto de ubicación**, pero no se utilizarán para fabricar una zona OTE ni para exigir un retroceso Fibonacci 62–79%.

## 3. Reglas de entrada

1. No calcular Fibonacci OTE.
2. No exigir un retrace 62–79%.
3. No sumar score por alcanzar una zona OTE.
4. No invalidar una operación porque el precio no alcance OTE.
5. La entrada se produce por **retorno/retest del FVG u OB válido** dejado por displacement y estructura confirmada.
6. Si el precio no retorna a la zona, no hay entrada.

## 4. FVG + OB como núcleo

La calidad de la zona debe derivarse de evidencia ICT observable:

- displacement;
- FVG válido y no consumido cuando corresponda;
- Order Block válido;
- relación con sweep/liquidez;
- BOS/CHOCH/MSS;
- alineación HTF/ITF/exec;
- stacking OB/FVG cuando exista.

No se introduce ningún sustituto de OTE como nuevo gate oculto.

## 5. Impacto en código

`analysis/ict_agent.py` deja de otorgar bonus de confianza por la presencia de `OTE` en `premium_discount_zone`.

La zona premium/discount queda como **evidencia contextual**, no como OTE.

## 6. Impacto documental

- `docs/reglas/ICT_RULEBOOK.md`: OTE eliminado del rulebook operativo.
- `docs/INDICE_AUTORIDAD.md`: la enmienda pasa a formar parte de la jerarquía vigente.
- `.hermes-worklog/2026-08-17_1530_OTE_REMOVAL.md`: queda registrada la migración.

## 7. No hacer

No reintroducir OTE bajo nombres alternativos como `optimal_entry`, `fib_entry`, `retracement_zone`, `ote_score` o equivalentes cuyo propósito sea reproducir el mismo gate.

**Principio:** ICT operativo centrado en **liquidez + estructura + displacement + FVG/OB + retorno a zona**.
