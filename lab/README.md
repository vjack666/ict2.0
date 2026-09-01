# Laboratorio de experimentos

Esta carpeta define la frontera del laboratorio. Los entrypoints viven en
`scripts/lab/learning/` y `scripts/lab/experiments/`; las rutas antiguas bajo
`scripts/` son wrappers de compatibilidad.

El laboratorio puede consumir snapshots canónicos y producir:

- datasets versionados;
- labels descriptivos;
- modelos;
- walk-forward y ablaciones;
- informes y evidencia.

No puede modificar `engine/`, Context State, AHF, LTF o Wyckoff de forma
automática. Toda promoción requiere propuesta, gate y shadow mode.
