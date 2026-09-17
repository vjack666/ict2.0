# Aprendizaje de patrones de entrada: diagnostico y exigencias

Fecha: 2026-09-17. Responsable: Codex, D3; revision independiente D5.
Estado del programa: WORKING. can_trade=false; entry_authorized=false.

## Objetivo del usuario

Exigir reconocimiento de modelos y patrones de entrada. La expectativa de
al menos dos entradas semanales proviene de backtests manuales empiricos sin
registro conservado, segun aclaracion expresa del usuario. Es una hipotesis,
no una medicion reproducible ni una cuota de operaciones. Universo y promedio
frente a minimo por semana siguen sin confirmar; EURUSD combinado es solo
el alcance provisional heredado del plan, no una respuesta del usuario.

## Evidencia ejecutada

Comando local, solo lectura de datos:

```powershell
.venv/Scripts/python.exe scripts/lab/experiments/audit_setup_order_information_v1.py
```

La prueba ejecuta las funciones puras reales `source_family` y
`extract_features` del entrenador mediante AST, sin inicializar TensorFlow.
Invierte `features_at_t.sequence`, manteniendo todo lo demas identico.

| Split | Filas | Orden invertido, features identicas | Etiqueta PASS | NO_ZONE |
| --- | ---: | ---: | ---: | ---: |
| TRAIN | 120 | 120 | 2 | 118 |
| VALIDATION | 96 | 96 | 0 | 96 |
| TEST_OOS | 76 | 76 | 4 | 72 |

Los tres SHA-256 de los datasets coinciden con `training_record.json` y
permanecen iguales despues de leerlos. Esto verifica integridad de esos
archivos, no calidad de etiquetas, causalidad, edge ni 60 fuentes originales.
La inspeccion de OOS es diagnostica ya publicada, sin ajuste de parametros;
no se presenta ese periodo como holdout virgen.

Causa concreta: `train_setup_quality_v1.py:113` convierte los eventos a un
conjunto; linea 133 codifica presencia. `encode_x` solo consume esas features.
El registro declara 36 entradas. El orden de eventos se pierde antes de la red.
No se ejecutaron predicciones ni entrenamiento nuevo: este resultado demuestra
perdida de informacion, no mide la exactitud ni la rentabilidad del modelo.

## Correcciones a la interpretacion del resumen

- Cero familias completas entre 292 filas seleccionadas no demuestra cero
  oportunidades en veinte anos. Tampoco dividir eventos seleccionados entre
  1036 semanas estima una tasa natural. Frecuencia: NO ESTIMABLE con esa muestra.
- NO_ZONE es el resultado de esa representacion y su etiquetado. Para atribuirlo
  al mercado hay que verificar fuente, detector, tiempo disponible y contexto.
- `reproduce_setup_quality_training.py` lee hashes y metricas existentes; no
  contiene llamada de entrenamiento. Su salida no prueba reentrenamiento.
- Dos PASS en TRAIN y cero en VALIDATION no permiten validar reconocimiento
  de entradas positivas. PASS de gramatica tampoco equivale a familia completa.
- Un resultado de clasificacion favorable no prueba comprension temporal.

## Exigencias verificables para continuar el plan existente

1. Forge/Helix: conservar eventos ordenados, tiempos de disponibilidad, edad,
   duracion, identidad de episodio y mascaras de faltantes en memoria. No
   inventar tiempos de eventos a partir de un unico decision_time. Mantener
   contexto H4/H1 y ejecucion M15 separados; reutilizar contratos por familia.
2. Forge/Probe: recorrer calendario continuo con cobertura verificada y estado
   entre velas; distinguir espera, invalidez y evidencia ausente. Registrar
   semanas sin setup y huecos por separado, y deduplicar eventos entre familias.
3. Helix: aprendizaje exploratorio autorizado por enmienda 2026-09-11. Comparar
   reglas, baseline estatico y modelo temporal pequeno; ajuste solo TRAIN.
   Medir precision y recall por familia/estado, falsos positivos, abstencion y
   calibracion con soporte por clase. No sustituir estas metricas por accuracy.
4. Vigil: FULL/PREFIX, futuro que no cambia pasado, grupos de episodios y purga
   temporal; ablaciones de orden/duracion/HTF/historia. Sensibilidad sola no
   prueba aprendizaje: exigir mejora util sobre baseline con incertidumbre.
5. Probe: medir promedio semanal y porcentaje de semanas con >=2 eventos,
   mediana, semanas cero y dispersion. Separar candidatos, entradas simuladas
   y trades cerrados; costes y edge tienen evaluacion posterior propia.
6. Forge: resolver contradicciones entre entregas antes de declarar entradas
   de pipeline aceptadas. No tratar limites del loader o falta de spread como
   demostracion de ausencia de OHLC util para reconocer patrones.

Fuentes, labels, splits y manifiestos permanecen inmutables. Transformaciones
en memoria y reportes/modelos nuevos siguen autorizados. Este informe no
modifica estrategias ni contratos, no reentrena, no despacha perfiles Hermes
y no declara corregido el encoder. La siguiente implementacion debe resolver
esa perdida de informacion y disponibilidad causal; repetir epocas no la resuelve.

Referencias: `docs/planificacion/PLAN_ICT_MULTIMODELO_INTRADIA_V1.md`,
`docs/contratos/SETUP_GRAMMAR_SUPERVISION_V1.md`,
`docs/contratos/ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md`.

## Revision independiente

`ict_assurance` reprodujo la prueba: 292/292 features identicas. Dictamen
BLOCKED para afirmar comprension temporal, no para continuar investigacion.
Ademas senala que el filtro M15 `time <= decision_time` del materializador
no acredita por si solo cierre de vela; falta prueba explicita de frontera
y FULL/PREFIX para esa ruta. Estos requisitos preceden una afirmacion causal.
La falta de registro manual no impide investigar: se construye evidencia
reproducible desde las fuentes existentes sin inventar el historial del usuario.
