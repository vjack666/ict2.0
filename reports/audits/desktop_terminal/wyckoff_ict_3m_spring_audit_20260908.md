# Auditoría de 3 meses — Spring/Test, ICT/Wyckoff y estocástico

**Periodo:** 2026-06-10 a 2026-09-08, EURUSD, M15 cerradas de MT5, sesiones
08:00–12:00 locales de Londres y Nueva York con DST. Solo lectura; cero órdenes.

## Método

Se aplicó el mismo proxy preregistrado de la auditoría de 14 días: rango móvil
de 32 velas, barrido bajo soporte con cierre de recuperación, estocástico 14,3,3
y MFE/MAE en las ocho velas siguientes. Un objetivo de 10 pips sirve solo para
comparar recorridos; no es una regla operativa.

## Resultado

| Métrica | Resultado |
|---|---:|
| Velas M15 cerradas | 6,872 |
| Candidatos Spring/Test | 44 |
| Con estocástico M15 simultáneo | 17 |
| MFE >= 10 pips | 11 |
| MFE medio | 6.47 pips |
| MAE medio | 9.45 pips |
| Candidatos Londres / Nueva York | 24 / 20 |

El proxy tuvo 11 recorridos favorables de 44 (25%), y 17 de 44 coincidencias
con estocástico (39%). Estas cifras no son win-rate ni edge: no incluyen la
dirección ICT confirmada, fase Wyckoff diaria congelada, spread, ejecución,
salida contractual ni deduplicación por episodio.

## Dictamen

La entrada anticipada merece una prueba de investigación separada, pero no
promoción automática. El MAE medio supera el umbral de 8 pips usado para mirar
las ocho velas, lo que confirma el riesgo de entrar demasiado pronto. El
estocástico reduce algunos casos, pero no basta para validar el Spring.

## Preparación futura

Congelar antes de cada sesión la zona y fase diaria Wyckoff; exigir Spring/Test
con cierre dentro del rango; registrar dirección ICT, liquidez, BOS/CHOCH,
retest M15, MFE/MAE y resultado; deduplicar por episodio; y comparar probe
pequeño contra entrada confirmada en meses fuera de muestra. Mientras no exista
el snapshot probabilístico histórico por vela, el bot seguirá en WAIT_SIGNAL.
