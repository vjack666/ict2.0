# Fase 1 — panel causal de displacement

AGENTE: Codex. DEPARTAMENTO: D3 / laboratorio; revisión D5 pendiente.
TAREA: materializar contrastes causales positivos/negativos separados de geometría, episodio y outcome; reconciliar detectores con evidencia por fila; cerrar M15 y FULL/PREFIX.
STATUS: COMPLETED para la materialización técnica; entrenamiento NO iniciado.

EVIDENCIA: corpus EURUSD M15 de 117134 filas, hash registrado en el manifiesto.
Panel por fila: 117134. Geometría positiva 38225; episodio positivo 23655;
outcome observable 117130. Reconciliación: NEITHER 87757, ENGINE_ONLY 25172,
AGREE 3768, RANGE_ONLY 437. Tests focalizados 3 passed.

ARCHIVOS: `scripts/lab/experiments/displacement_phase1.py`,
`tests/test_displacement_phase1.py`,
`reports/ict_temporal_v1/helix/displacement_v1/`.

CONTRATO: M15 UTC, cálculos causales hasta el cierre de la fila, horizonte de
outcome audit-only, prefijo estable para salidas causales, sin modificación de
fuentes, `training=false`, `can_trade=false`.

RIESGOS: las dos rutas son proxies distintos y no existe equivalencia semántica;
el panel no acredita reconocimiento externo, edge ni producción. La cobertura
de outcome es futura y no puede entrar como feature del alumno.

SIGUIENTE ACCIÓN: revisar con auditoría independiente la especificación de
fronteras y decidir si los contrastes pasan a fase 2; no entrenar antes de esa
revisión.
