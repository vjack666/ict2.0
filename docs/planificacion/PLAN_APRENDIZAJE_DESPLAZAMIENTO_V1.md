# Plan de aprendizaje de desplazamiento v1

Fecha: 2026-09-17. Responsable del programa: D3 / Helix; coordinacion: Forge.
Estado: READY — plan revisado; implementacion y entrenamiento pendientes.
Autor: Codex. Alcance de esta entrega: preparar y revisar el plan solicitado.
LOCAL_ONLY; can_trade=false; entry_authorized=false.

Revision independiente: ict_assurance aprobo la coherencia de la planificacion
el 2026-09-17; no es validacion de resultados de entrenamiento.

## 1. Objetivo observable

Que la IA identifique un movimiento de desplazamiento, su direccion, intensidad,
inicio y momento de confirmacion, y distinga su funcion dentro del patron ICT.
Debe indicar evidencia observable y abstenerse cuando falte historia o contexto.
Reconocer desplazamiento no equivale a reconocer una entrada completa.
Las dos entradas semanales son una hipotesis posterior del programa multimodelo;
no son objetivo de optimizacion, etiqueta ni criterio de exito de este modulo.

Como definicion didactica inicial: movimiento direccional con expansion respecto
a su contexto previo, cuerpo dominante y avance del precio; su calificacion ICT
requiere ademas las relaciones exigidas por el contrato aplicable. Una vela grande
aislada no basta. OHLC permite medir un patron de precio, no identificar al actor
que negocio: la expresion institucional se conserva como terminologia de tesis,
sin convertirla en una etiqueta empirica de identidad institucional.

## 2. Punto de partida verificado

- `engine/detectors/displacement.py`: proxy M15 con cuerpo/rango >=0.50,
  cuerpo >=1.5 pips y cierre fuera de extremos de dos velas previas. El texto
  del modulo dice >=60%; documentacion y valor predeterminado no coinciden.
- `detectors/displacement.py` y `tools/displacement.py`: cuerpo mayor a 1.5
  veces rango medio de 14 velas, mechas menores al 40%. Incluyen la vela actual
  en el promedio y sustituyen calentamiento ausente por 1e-9. Revisar esta
  sustitucion antes de utilizar su salida como profesor.
- `engine/market_features.py` consume `detectors.displacement`; el materializador
  fijo usa `engine.detectors.displacement`. No existe equivalencia demostrada.
- `docs/ict/SPEC_TESIS_FORMAL.md`, seccion DISPLACEMENT: velas cerradas tras sweep,
  cuerpo >70%; 50-70% debil, y umbral explicitamente calibrable. La tesis y POI
  agregan relaciones con contexto y PD Array; no son solo geometria.
- `materialize_setup_grammar_dataset_v1_fixed.py:277`: etiqueta
  `PRESENT_UNGRADED` por presencia del nombre DISPLACEMENT en un conjunto.
- Auditoria independiente: las 292 filas existentes tienen esa misma etiqueta
  y el flag de presencia constante. El modelo no tiene una salida especifica
  para displacement. No hay contraste supervisado fuerte/debil/ausente en ese corpus.
- El entrenador actual pierde orden de eventos. La prueba independiente del
  17 de septiembre dio features identicas al invertir 292/292 secuencias.
- `run_displacement_profile_comparison.py` predice por defecto `label_end_6`;
  comparar perfiles de outcome no demuestra haber aprendido que es desplazamiento.

No modificar estos detectores ni etiquetas como parte de redactar este plan.

## 3. Que debe aprender, en capas

| Capa | Pregunta | Evidencia y salidas propuestas |
| --- | --- | --- |
| Geometria | Como es el movimiento? | Cuerpo/rango, mechas, posicion del cierre, direccion, rango y cuerpo relativos al pasado. |
| Episodio | Hay expansion direccional y cuando aparece? | Velas ordenadas, avance neto, solapamiento, retroceso, duracion; candidato, confirmado o indeterminado. |
| Contexto ICT | Que papel cumple en este patron? | Sweep previo cuando se exija, nivel estructural ya conocido, relacion con FVG/OB y contexto HTF disponible. |

Esquema propuesto: `geometric_strength` (NONE/WEAK/STRONG/UNKNOWN),
`direction` (UP/DOWN/NONE/UNKNOWN), `ict_context_status`
(SUPPORTED/NOT_SUPPORTED/PENDING/UNKNOWN), inicio, confirmacion, available_at,
probabilidades por clase y razones con valores medidos. Las fronteras y el uso
de WEAK se cierran en fase 1; no se deducen automaticamente de un porcentaje.
Una geometria fuerte puede tener contexto ICT no confirmado. FVG todavia no
observable significa PENDING, no confirmacion anticipada ni negativo automatico.
Estas son salidas propias del nuevo aprendizaje de desplazamiento, no inferencias
extraidas de la cabeza de outcome ni de la decision general de setup_quality_v1.

## 4. Fases, responsables y entregables

| Fase | Responsable | Trabajo | Entrega y condicion de salida |
| --- | --- | --- | --- |
| 1. Profesor coherente | Orion D6 + Forge D2; revisa Vigil D5 | Contrastar tesis, configuraciones y consumidores; separar geometria de setup contextual; fijar casos frontera, prioridad de contratos y reloj. | Especificacion versionada y tabla documento/regla/consumidor/test; contradicciones resueltas o marcadas no evaluables. |
| 2. Ejemplos causales | Nexus D4 + Probe D6 | Inventariar fuentes existentes y cobertura M15; cargar periodos continuos en memoria; comparar episodios positivos, negativos y ambiguos. | Informe de soporte por clase/direccion/periodo, hashes y receta reproducible; ninguna clase evaluada con soporte cero. |
| 3. Representacion | Forge D2 + Helix D3 | Preservar velas, orden, duracion, mascaras y contexto conocido; normalizar solo con TRAIN; separar salidas del profesor de entradas del alumno. | Lector/tensor con pruebas de cierre, disponibilidad y FULL/PREFIX; trazabilidad de cada variable a sus fuentes. |
| 4. Aprendizaje gradual | Helix D3 | Comparar regla congelada, baseline tabular y modelo temporal pequeno. Primero geometria, despues episodios, finalmente contexto. | Modelos y reportes nuevos, semillas y configuracion; learning curves y errores por clase. |
| 5. Examen independiente | Vigil D5 | Reproducir evaluacion, revisar ejemplos sin ver prediccion, medir falsos positivos, omisiones, abstencion y ablaciones. | Dictamen RECOGNITION_SUPPORTED, REVIEW_INSUFFICIENT_EVIDENCE o FAILED_CRITERIA, sin confundirlo con edge. |
| 6. Entrega educativa | Forge D2 + Ledger D1 | Mostrar replay hasta decision_time, zona del impulso, evidencia y razones; mantener resultado fuera de ejecucion. | Ficha por caso y tabla de fallos; documentacion, auditoria y commit local selectivo. |

Dependencias: 1 y el inventario de 2 pueden avanzar en paralelo; etiquetado
experimental en memoria requiere 1; 3 requiere reloj/datos de 2; 4 requiere
3; 5 requiere 4. Quien construye no aprueba su propia evaluacion. Estos son
responsables propuestos del plan existente, no perfiles despachados en esta tarea.

## 5. Curriculum de ejemplos

1. Contrastes simples: cuerpo dominante contra vela de mecha larga; mismo
   porcentaje de cuerpo en vela diminuta y expansion grande respecto al pasado;
   direccion alcista y bajista. Incluir doji, rango cero y calentamiento insuficiente.
2. Contexto local: expansion fuera de consolidacion, avance con solapamiento,
   vela grande dentro de rango, ruptura solo por mecha y cierre realmente fuera
   de un nivel conocido. Separar 1 vela de impulso de episodio de varias velas.
3. Contexto ICT: mismo impulso con sweep previo verificable o sin el; FVG/OB
   vinculado al impulso o solo cercano; estructura confirmada o pendiente;
   HTF favorable, contrario o desconocido. El desacuerdo HTF no borra geometria.
4. Casos dificiles y fallos: movimiento fuerte que despues retrocede, movimiento
   ordinario que despues gana recorrido y final de datos sin confirmacion.
   El resultado posterior no redefine lo que era observable en decision_time.

Seleccion estratificada para docencia; evaluacion sobre calendario continuo y
prevalencia natural. Los casos sinteticos sirven para tests y contrastes, nunca
para acreditar poblacion real o frecuencia. El usuario puede aportar ejemplos
mas adelante, pero no se exige recuperar su historial manual para comenzar.

## 6. Datos, tiempo y supervision

- Foco inicial propuesto: EURUSD M15, con H1/H4 cuando existan fuentes verificadas.
  No extender a otros simbolos usando el factor fijo 0.0001 sin contrato de pip.
- Fuentes/corpus/labels/splits/manifiestos existentes inmutables. Sin descarga
  ni nuevos corpus persistidos. Transformaciones y supervision derivada solo en
  memoria; guardar codigo, configuracion, modelos, predicciones y reportes nuevos.
- Respetar splits persistidos del experimento seleccionado. No copiar fronteras
  B1 a otro corpus por analogia. Evaluar primero DESIGN/TRAIN; declarar que OOS
  ya inspeccionado no es holdout virgen. Congelar el protocolo antes de validacion.
- Agrupar ventanas del mismo episodio; purgar horizontes solapados entre splits.
  Estadisticas de escala, balanceo y seleccion de hiperparametros solo TRAIN.
- Barras cerradas; distinguir apertura/cierre, formacion/confirmacion/available_at.
  FVG de tres velas solo disponible al cerrar la tercera; pivote confirmado
  despues conserva su hora de confirmacion. Nunca backdatear evidencia.
- Usar contexto previo excluyendo vela evaluada para la normalizacion propuesta;
  marcar la diferencia frente al baseline actual, que incluye esa vela. No afirmar
  que incluir la vela cerrada sea por si mismo lookahead. Historia corta => UNKNOWN.
- Ordenar eventos por disponibilidad, conservando simultaneidad. Resolver en fase
  1 el alcance de secuencia de espera y DAG de evidencias hermanas; no inventar
  un orden estricto universal entre BOS, FVG y displacement.
- Prohibido alimentar al alumno con `displacement=true`, `displacement_quality`,
  etiqueta objetivo o consecuencia futura. Variables OHLC causales si se permiten.
- Etiquetas de reglas son supervision debil: medir fidelidad al profesor no prueba
  comprension externa. Vigil revisa un panel separado por rubrica, ocultando salidas
  del profesor/modelo y futuro; registra acuerdo y discrepancias en informe, sin
  reescribir etiquetas ni materializar corpus. Si no hay referencia independiente,
  limitar el dictamen a imitacion del profesor, aunque la exactitud sea alta.

## 7. Primer ciclo de entrenamiento y examen

Prerregistro propuesto: un baseline de reglas congeladas, un clasificador tabular
simple y una GRU pequena sobre secuencias causales; no busqueda masiva. Ventana
inicial de 32 M15 cerradas y resumen HTF as-of es una configuracion experimental,
no un plazo de caducidad del patron. Elegirla o corregirla con TRAIN antes de
congelar validacion. Un episodio mayor conserva estado y edad, no se descarta.
Tres semillas fijas (17, 42, 101), hasta 50 epocas por semilla, early stopping
con paciencia 5 en una particion interna temporal de TRAIN con purga. El examen
externo no selecciona epocas. Registrar recursos y tiempos reales del piloto;
no prometer duracion antes de medirlos. Menor soporte permite ensayo exploratorio,
pero no eliminar el reporte de insuficiencia.

Metricas obligatorias: precision/recall/F1 por clase y direccion, matriz de
confusion, PR-AUC cuando aplique, calibracion, cobertura de decisiones,
abstenciones, error de inicio/confirmacion y falsos positivos por 1000 velas.
Reportar soporte efectivo por episodios y periodos, incluyendo indecisos;
intervalos de incertidumbre agrupados por episodio/semana, no velas duplicadas.

Criterios preliminares para congelar en fase 1 (metas de investigacion, no
estandares ICT ni promesas): precision >=0.85 y recall >=0.75 para STRONG,
en ambas direcciones, a cobertura >=0.60; abstenciones positivas cuentan como
omisiones al medir recall global. Intervalo del 95% de precision/recall con
semiancho <=0.10; si no alcanza soporte, REVIEW. No ajustar estos numeros al
ver validacion ni relajar reglas para conseguir dos entradas por semana.
La superioridad temporal requiere mejora frente al tabular con incertidumbre
compatible con mejora en la metrica preregistrada, no solo reaccion a permutaciones.
Si reglas bastan y la red no agrega valor, entregar ese resultado explicitamente.

Pruebas necesarias:

- FULL/PREFIX: agregar velas futuras no cambia salidas pasadas; batch y paso a
  paso coinciden. Frontera exacta de cierre y calentamiento incompleto.
- Fronteras exactas 0.50/0.60/0.70 y multiplo 1.5, rangos cero, escala de precio
  y diferencias entre rutas; documentar > frente a >=. Paridad solo cuando ambas
  rutas deban implementar el mismo contrato, no forzar equivalencia de proxies.
- Contrastes semanticos de orden/duracion, sin cambiar orden irrelevante de
  evidencias hermanas para forzar un fallo. Una prediccion distinta no basta:
  debe mejorar la respuesta correcta en casos evaluables.
- Ablacion de historia y HTF; para geometria la ausencia de HTF no debe borrar
  necesariamente el impulso. Para contexto puede producir UNKNOWN/PENDING.
- Un movimiento no pierde su etiqueta observable porque luego fracase. Fin de
  historico pendiente no se etiqueta como NO_DISPLACEMENT.
- Tabla separada: tests tecnicos, calidad de reconocimiento y edge economico.

## 8. Entregables y cierre

Crear resultados nuevos bajo `reports/ict_temporal_v1/helix/displacement_v1/`
y auditoria de Vigil en su propia carpeta, con run_id, hashes, commit, receta,
metricas y limites. Los modulos nuevos tendran write sets asignados antes de
despachar; codigo de deteccion compartido pertenece a Forge. Sin sobreescritura.

Primera entrega exigible: contrato resuelto + panel docente reproducible +
conteos reales de clases y cobertura + tests de reloj/representacion. La segunda
entrega es el entrenamiento comparado. La tercera es el examen independiente.
No se declara aprendizaje demostrado por crear archivos, producir un modelo
o superar accuracy con fuerte desbalance. Ninguna fase autoriza trading.

Referencias locales: `docs/ict/SPEC_TESIS_FORMAL.md`, `docs/ict/20_TESIS_ICT.md`,
`docs/ict/21_POI.md`, `docs/contratos/SETUP_GRAMMAR_SUPERVISION_V1.md`,
`docs/contratos/CONTRATO_HISTORICAL_EVENT_OBJECT_PRODUCER_V1.md`,
`docs/tesis/SDD_SEQUENCE_EVENT_WAIT.md`,
`docs/contratos/ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md` y
`reports/audits/experiments/ai/entry_pattern_learning_readiness_20260917.md`.
