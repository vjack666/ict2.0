# Contrato — Relación FVG ↔ OB

**Estado:** NORMATIVO  
**Propósito:** conectar los detectores canónicos FVG y Order Block sin convertir automáticamente la confluencia en una entrada.

## Regla canónica — modo `strict` (default)

Una relación `FVG_OB_CAUSAL` existe cuando:

1. ambos objetos son canónicos (`FVG` y `ORDER_BLOCK`);
2. sus zonas de precio tienen intersección positiva;
3. **orden causal ICT:** el OB se forma **antes** de la confirmación del FVG:
   - `ob.candidate_bar` (huella) ≤ `fvg.confirmation_bar`;
   - `ob.confirmation_bar` ≤ `fvg.confirmation_bar`;
   - `ob.candidate_bar` < `fvg.confirmation_bar` (no degenerado en la misma barra de confirmación);
4. el lag `fvg.confirmation_bar - ob.candidate_bar` ≤ `max_bars_apart` (por defecto 20);
5. sus direcciones coinciden, salvo que una llamada permita direcciones opuestas;
6. el `CausalLink` tiene **siempre** `parent=OB`, `child=FVG`.

Esto modela la narrativa: *el OB es el origen del impulso que dejó el FVG*, no un solape geométrico simétrico.

## Modo `symmetric` (legado / ablación)

`FVG_OB_OVERLAP` con `|confirm_fvg - confirm_ob| ≤ max_bars_apart` sin imponer quién va primero. Solo para comparación; **no** es la regla operativa.

## Lo que NO significa

`FVG_OB_CAUSAL` / `FVG_OB_OVERLAP` no significan automáticamente:

- setup válido;
- entrada;
- retest;
- edge;
- PnL positivo.

Es una **relación de objetos** que habilita la siguiente capa de contexto/setup.

## Anti-look-ahead

El par sólo puede existir dentro de la ventana temporal definida. No se permite crear una relación usando un OB posterior a la confirmación del FVG (modo strict).

## Salida

```text
FVGOBRelation
├── fvg_id
├── ob_id
├── relation          # FVG_OB_CAUSAL | FVG_OB_OVERLAP
├── direction
├── overlap_low
├── overlap_high
├── temporal_ok
├── bars_apart
├── ob_anchor_bar
├── fvg_confirm_bar
└── causal_order      # OB_BEFORE_FVG | SYMMETRIC
```

## Gate

PASS requiere:

- tests de solapamiento con OB **antes** del FVG;
- rechazo de OB posterior al FVG (strict);
- rechazo por dirección opuesta;
- rechazo por distancia temporal;
- `CausalLink` con parent=OB en modo strict;
- validación temporal de `CausalLink`.

La conexión debe medirse en el Funnel 20Y (strict vs symmetric) antes de usarla como filtro de setup.
