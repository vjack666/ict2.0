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


## ICT + Wyckoff + IA temporal

Wyckoff forma parte del mismo sistema de investigación; no debe copiarse a un
proyecto aislado ni desaparecer durante la reorganización.

La cadena conceptual preservada es:

```text
D1 → H4 → H1 → M15 → M5/M1
      │
      ├── contexto ICT
      └── contexto Wyckoff
              ↓
        secuencia temporal
              ↓
         IA / shadow
```

El código canónico de Wyckoff permanece bajo `engine/Wyckoff/`, su adaptación
bajo `analysis/wyckoff_agent.py`, su teoría bajo `docs/wyckoff/` y sus
pruebas bajo `tests/`.

Una GRU solo se entrena después de materializar episodios realmente ordenados;
la presencia de flags estáticos no sustituye memoria temporal.
