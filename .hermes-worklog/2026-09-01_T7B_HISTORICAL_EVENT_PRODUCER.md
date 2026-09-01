# T7b — productor histórico BOS/displacement

## Estado

`BLOCKED`: productor canónico implementado y validado; T7b real ejecutada, pero
la población de enero de 2025 no contiene setups completos ni episodios.

## Trabajo realizado

- Se creó `engine/historical_event_objects.py`, componiendo las autoridades
  existentes de OB, FVG, BOS y displacement.
- BOS usa `bos_dir`; no usa `bos_real`, cuyo score incorpora etiqueta futura.
- Los IDs son deterministas y el lineage solo apunta de hijo a padres ya
  publicados.
- BOS/displacement son eventos inmutables; el lifecycle sigue reservado a
  objetos zonales.
- Se añadieron pruebas de determinismo, lineage temporal y FULL/PREFIX.
- Se ejecutó T7b sobre diciembre de 2024 como warmup y enero de 2025 como
  ventana evaluada, sin edge, IA, MT5, SL/TP ni optimización.

## Evidencia T7b

- Commit ejecutado: `d9b0e1d`.
- Dataset hash: `145229219abea0abca63734b28ed65e17afbb809661ef966afa2b79c31e1a25c`.
- Productor: 11 OB H4, 29 FVG M15 vinculados, 10 BOS H4 vinculados y 4
  displacement M15 vinculados; uno de estos displacement pertenece a enero.
- Determinismo, FULL/PREFIX 25/50/75/90 y manifest de chunks: PASS.
- Setups completos: 0; elegibles: 0; episodios: 0. Estado global: `FAIL`.
- Integridad mecánica: PASS; procedencia formal: `BLOCKED_PROVENANCE`.

## Investigación de causa raíz

El displacement de enero aparece después de que su POI H4 ya fue mitigado e
invalidado, por lo que Setup Builder correctamente no fabrica un setup. Se
probó la hipótesis alternativa BOS M15 + exigencia ACTIVE en toda la cadena y
se inventariaron cronológicamente todas las ventanas mensuales 2021–2025: no
produjo ningún displacement con cadena completa. La hipótesis se descartó y
no se incorporó al código.

## Decisión

No ampliar meses, buscar edge ni relajar gates. Antes de una T7b PASS hace
falta definir y preregistrar el DAG temporal correcto entre BOS, displacement
y FVG de ejecución. La teoría permite que el FVG aparezca durante o después del
displacement; imponer siempre `FVG→BOS→displacement` puede ser una restricción
semántica incorrecta. Ese cambio requiere contrato y pruebas antes de correr
otra ventana.

## Riesgos

- El productor es causal, pero su composición semántica aún no demuestra una
  población completa real.
- El artefacto grande de replay queda local y sin versionar; el reporte de
  auditoría conserva hashes, gates y conteos.
- Los parquets y demás artefactos no relacionados del worktree no se tocaron.

