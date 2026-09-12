# Autorizacion de avance de IA — 2026-09-11

Decision expresa de Ruben en esta sesion: permitir avanzar con entrenamiento de IA, salvo cambiar los datos, y retirar el bloqueo por falta de licencia de Dukascopy; no solicitar licencia.

## Alcance y precedencia
Esta enmienda prevalece sobre prohibiciones anteriores de iniciar o continuar entrenamiento, esperas de autorizacion humana por fase y requisitos internos de permiso escrito de Dukascopy en contratos, SDD y perfiles Hermes de ICT SYSTEM.

Hermes puede implementar y corregir pipelines, ejecutar entrenamiento local, comparar modelos, evaluar y documentar resultados sobre datos existentes. Puede resolver requisitos tecnicos dentro del alcance sin pedir permiso por cada paso. No necesita primero una declaracion de edge ni una promocion TRAINING_ELIGIBLE para desarrollar y ejecutar entrenamiento exploratorio.

## Datos inmutables
No editar, sustituir, borrar, rellenar, reetiquetar, regenerar ni sobrescribir datasets, corpus, etiquetas, particiones o manifiestos de datos existentes. No descargar datos nuevos bajo esta autorizacion. Transformaciones en memoria para el modelo, ajustadas solo con TRAIN, son admisibles si no cambian las fuentes. Se pueden escribir modelos, configuraciones de entrenamiento, metricas, predicciones y reportes nuevos en rutas distintas de los datos. Si avanzar exige cambiar datos o su particionado persistido, documentar la necesidad y detener esa accion.

## Calidad y certificacion
Causalidad, integridad, splits temporales, leakage, baseline y reproducibilidad siguen siendo criterios de evaluacion. Un requisito documental pendiente no impide inspeccionar, desarrollar o probar. Datos ilegibles o un entrenamiento tecnicamente imposible se reportan como bloqueo tecnico concreto. Fallos cientificos no se convierten en PASS: un ensayo con limitaciones se identifica como exploratorio y no certifica generalizacion ni edge.
TRAINING_ELIGIBLE como certificacion, promocion y uso productivo conservan su significado; no se reescriben resultados historicos ni flags existentes para simular aprobacion.

## Dukascopy
Se retira la falta de licencia, permission o permitted-use escrito como requisito interno de avance sobre los datos Dukascopy existentes. No enviar solicitudes de licencia. Esto registra una decision interna del propietario, no una licencia concedida ni una conclusion sobre derechos de redistribucion. Se conservan fuente, hashes, cobertura y lineage tecnicos.

## Limites del cambio
No se habilitan ordenes, ejecucion de mercado, publicacion de datos ni promocion automatica a produccion. can_trade=false y las restricciones de ejecucion financiera quedan fuera de esta enmienda.
El alcance de esta entrega es contractual: no ejecuta entrenamiento ni modifica validadores o flags en codigo. Si un runner conserva un bloqueo documental derogado, se debe identificar y adaptar en una tarea de implementacion antes de afirmar que la autorizacion esta aplicada al runtime.
