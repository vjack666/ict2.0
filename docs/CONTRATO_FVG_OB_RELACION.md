# Contrato — Relación FVG ↔ OB

**Estado:** NORMATIVO
**Propósito:** conectar los detectores canónicos FVG y Order Block sin convertir automáticamente la confluencia en una entrada.

## Regla canónica

Una relación `FVG_OB_OVERLAP` existe cuando:

1. ambos objetos son canónicos (`FVG` y `ORDER_BLOCK`);
2. sus zonas de precio tienen intersección positiva;
3. sus barras están separadas como máximo `max_bars_apart` (por defecto 20);
4. sus direcciones coinciden, salvo que una llamada explícitamente permita direcciones opuestas;
5. el enlace conserva el orden temporal mediante `CausalLink`.

## Lo que NO significa

`FVG_OB_OVERLAP` no significa automáticamente:

- setup válido;
- entrada;
- retest;
- edge;
- PnL positivo.

Es una **relación de objetos** que habilita la siguiente capa de contexto/setup.

## Anti-look-ahead

El par sólo puede existir dentro de la ventana temporal definida. No se permite crear una relación usando un objeto fuera de la ventana causal.

## Salida

```text
FVGOBRelation
├── fvg_id
├── ob_id
├── relation
├── direction
├── overlap_low
├── overlap_high
├── temporal_ok
└── bars_apart
```

La relación puede convertirse a `CausalLink` para integrarse con lineage.

## Gate

PASS requiere:

- tests de solapamiento;
- rechazo por dirección opuesta;
- rechazo por distancia temporal;
- ausencia de enlaces duplicados;
- validación temporal de `CausalLink`.

La conexión debe medirse de nuevo en el Funnel 20Y antes de usarla como filtro de setup.
