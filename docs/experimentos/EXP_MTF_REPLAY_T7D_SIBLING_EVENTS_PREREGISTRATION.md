# Preregistro — T7d eventos M15 hermanos bajo POI H4

## Motivo

T7c demostró en la ventana congelada que el displacement alcista del
2025-01-17 15:15 UTC precede al BOS confirmado de 15:30 UTC. Por tanto,
`BOS→displacement` no es una precedencia universal. T7c se conserva como FAIL;
esta enmienda se registra antes de ejecutar T7d.

## Productor congelado

- DAG: `OB H4 → {FVG M15, BOS M15, displacement M15}`.
- Los hijos solo apuntan al POI ya publicado y ACTIVE.
- FVG exige mismo sentido y solapamiento geométrico.
- BOS y displacement exigen mismo sentido.
- Ventana POI→hijo: 120 horas.
- Setup Builder exige POI/FVG ACTIVE y presencia visible de BOS y displacement;
  el setup no puede aparecer antes del último componente.

Datos, hashes, cortes FULL/PREFIX, gates y prohibiciones son idénticos a T7c.
No se cambia mes, detector, etiqueta ni outcome. Un nuevo fallo bloquea el
entrenamiento y se conserva sin modificar este preregistro.
