# Reporte Simple — Avance Entrenamiento IA / TensorFlow

**Fecha:** 2026-09-16
**Commit actual:** `c495efc feat(ai): materialize failure anatomy dataset`
**Para:** lector sin formación técnica profunda
**Política:** `can_trade=false`, `shadow_mode=true`

---

## 1. ¿Qué es una red neuronal?

Una red neuronal es un programa matemático que aprende patrones a partir de
ejemplos.

Imagina que le das a un alumno 100 tarjetas con preguntas y respuestas, y le
pides que aprenda a responder tarjetas nuevas. La red hace algo similar:

1. Mira los datos de entrada.
2. Propone una respuesta.
3. Compara su propuesta con la respuesta real.
4. Ajusta su “memoria interna” para cometer menos errores la próxima vez.

Esto no es magia y no es inteligencia humana. Es estadística organizada con
estructuras matemáticas.

En ICT SYSTEM, la red no maneja dinero, no abre operaciones y no decide nada
en tiempo real. Solo estudia patrones históricos en un laboratorio local.

---

## 2. ¿Qué significa “aprendió”?

Significa que el modelo ya no responde al azar.

Por ejemplo, si la red solo adivinara, su acierto sería cercano al nivel de azar
o al peor de los casos. Si “aprendió”, su respuesta es mejor que esa línea de
base mínima.

Pero aprender no es lo mismo que ser bueno. Una red puede aprender algo y
aún así cometer muchos errores o confiarse demasiado. Aprender es una señal de
progreso, no una certificación de confiabilidad.

---

## 3. ¿Qué significan `continuation`, `reversal` y `failure`?

La red estudia tres tipos de resultado posible para una secuencia ICT:

- `continuation`: la tendencia sigue caminando en la misma dirección.
  Es como un peatón que sigue cruzando la calle sin detenerse.

- `reversal`: la dirección gira y camina al revés.
  Es como un semáforo que cambia de sentido a mitad del cruce.

- `failure`: la secuencia parecía válida, pero pierde fuerza y no alcanza el
  resultado esperado.
  Es como una señal de tráfico que se ve bien, pero el peatón no logra
  terminar la cruzada como se planeó.

---

## 4. ¿Por qué detectar fallos es más difícil?

Por varias razones:

1. **Los fallos son menos frecuentes.**
   Los datos tienen menos ejemplos de `failure` que de `continuation` o
   `reversal`. Menos ejemplos significa más difícil aprender.

2. **Los fallos son más variados.**
   Puede fallar por contexto adverso, conflicto de temporalidades, estructura
   débil, ambigüedad de dirección, y otras razones. No hay un solo patrón.

3. **Lo que parece un fallo a veces es solo una secuencia larga.**
   El mercado no siempre resuelve rápido. Una secuencia que parece fallar a
   6 barras puede haberse resuelto después. Eso hace más ventoso aprender con
   etiquetas a horizonte corto.

4. **El ruido se parece al fallo.**
   Muchas veces una secuencia “necesita más información” y eso puede parecerse
   a un fallo real.

Por eso, incluso cuando la red mejora, `failure` sigue siendo la clase más
débil.

---

## 5. ¿Qué se logró con v1.001?

Se entrenó la primera versión con 100 eventos y 6 features.

Resultado:
- `failure` colapsó completamente: no detectó ningún fallo.
- accuracy total: 0.4500.
- estado: BLOCKED/REVIEW.

En palabras simples: la red no aprendió a reconocer fallos. Aprendió parte de
`continuation` y `reversal`, pero `failure` se quedó en cero.

---

## 6. ¿Qué se logró con v1.002?

Se agregaron más eventos: 292 en total.

Resultado:
- `failure` ya no colapsó totalmente.
- failure recall: 0.0769.
- failure F1: 0.1290.
- estado: REVIEW.

En palabras simples: la red empezó a captar algún fallo, pero muy poco.
Todavía no es útil desde el punto de vista analítico fuerte.

---

## 7. ¿Qué se logró con v1.003?

Se ampliaron las features a 41 y se midió con más rigor.

Resultado:
- failure recall: 0.2308.
- failure F1: 0.2609.
- accuracy: 0.5132.
- estado: REVIEW.

En palabras simples: la red mejoró notablemente en detectar fallos respecto a
v1.002. Es el avance más claro de la serie.

Pero aún así:
- Solo detecta un poco más de un 23% de los fallos reales en OOS.
- El soporte de fallos en OOS es 26 eventos, menos de 30.
- Por eso el estado sigue siendo REVIEW, no PASS.

---

## 8. ¿Qué se materializó con `failure_anatomy_v1`?

Se creó un nuevo dataset de laboratorio separado, pensado para estudiar la
anatomía del fallo antes de intentar predecir el resultado general.

Tiene:
- TRAIN: 120 filas, 25 failure.
- VALIDATION: 96 filas, 19 failure.
- TEST_OOS: 76 filas, 26 failure.
- Drivers candidatos organizados por taxonomía.

En palabras simples: en lugar de preguntar “¿qué resultado tendrá esta
secuencia?”, se pregunta “¿esta secuencia tiene síntomas que la hacen propensa
a fallar?”. Es como pasar de un diagnóstico general a una revisión médica
más enfocada.

---

## 9. ¿Qué aprendió `failure_risk_v1`?

`failure_risk_v1` es un modelo nuevo entrenado sobre el dataset
`failure_anatomy_v1`. Su trabajo es responder una pregunta diferente a la de las
versiones anteriores: no “¿qué resultado tendrá esta secuencia?” sino “¿esta
secuencia tiene alto riesgo de fallar?”.

Resultado en OOS:
- Detecta un 34.62% de los fallos reales, frente al 23.08% de v1.003.
- Mejora la F1 de failure de 0.2609 a 0.4091.
- Mejora la accuracy de 0.5132 a 0.6579.
- Mejora el ROC-AUC a 0.6108, por encima del baseline de regresión logística (0.5254).

En palabras simples: el nuevo modelo reconoce más fallos que v1.003 y lo hace
con un nivel de detección claro por encima de lo trivial. Eso es aprendizaje real
respecto a la línea anterior.

Pero también tiene problemas importantes:
- Memoriza demasiado los datos de entrenamiento: su rendimiento en entrenamiento
  es mucho mejor que en OOS.
- Sus probabilidades no son muy confiables: cuando dice 0.7 de riesgo, en la
  realidad ve menos fallos de los esperados.
- Su curva de precisión-recall es ligeramente peor que la de un modelo lineal
  simple, así que la mejora en recall viene con un costo en falsos positivos.

Estado: REVIEW, no PASS.

---

## 10. ¿Qué significa sobreajuste?

Imagina que un alumno estudia solo las preguntas del examen anterior. En el
examen de práctica obtiene nota perfecta, pero el examen real es distinto y
su nota baja.

Eso es sobreajuste: el modelo funciona muy bien con lo que ya vio, pero se
porta mucho peor con datos nuevos. El modelo aprende a reconocer los ejemplos
de entrenamiento en lugar de aprender un patrón general.

`failure_risk_v1` tiene este problema: su ROC-AUC en entrenamiento es 0.9408,
pero en OOS baja a 0.6108. Esa diferencia grande es señal de sobreajuste. No es
un modelo malo en absoluto, pero tiene una brecha importante entre lo que sabe y
lo que generaliza.

---

## 11. ¿Qué significa mala calibración?

Imagina un pronóstico del tiempo que dice “70% de lluvia”. Si en la realidad,
de 10 días que pronosticó 70% de lluvia, solo 3 llovieron, el pronóstico es
poco confiable. La red no es “mala” necesariamente en su ordenamiento, pero sus
números absolutos no reflejan bien la probabilidad real.

`failure_risk_v1` tiene un ECE de 0.1952 en OOS, lo que indica que sus
probabilidades y la realidad se separan de forma notable. Esto no anula su
capacidad de detectar más fallos, pero impide leer sus números como si fueran
probabilidades reales listas para operar.

---

## 12. ¿Por qué el modelo no pasa a PASS a pesar de mejorar?

Hay varios motivos combinados:

1. **Muestra pequeña.**
   Solo hay 26 fallos en OOS. Con esa cantidad, una diferencia de uno o dos
   ejemplos cambia las métricas noticeablemente.

2. **Sobreajuste.**
   La brecha entre entrenamiento y OOS es grande. Eso resta confianza en que el
   modelo aprendió algo general.

3. **Calibración deficiente.**
   Las probabilidades del modelo no son lo bastante honestas. Eso importa si en
   el futuro se quiere usar el riesgo de failure como probabilidad de decisión.

4. **PR-AUC inferior al baseline.**
   El modelo mejora el recall, pero a costa de más falsos positivos en la región
   de alta probabilidad. Eso reduce su utilidad en escenarios donde la precisión
   importa tanto como el recall.

Por todas esas razones, el modelo no es PASS. Es un avance real, pero no
suficiente para certificar confiabilidad.

---

## 13. ¿Esto autoriza trading, DEMO, live signal o producción?

No.

Explícitamente:

- NO trading.
- NO DEMO.
- NO live signal.
- NO producción.
- NO promoción automática.

El estado actual es diagnóstico de laboratorio.

La regla es clara: **can_trade=false permanece intacto.**

El entrenamiento no ha logrado PASS científico. Solo hay aprendizaje medible y
mejoras parciales. Eso no autoriza nada operativo.

---

## 14. ¿Qué significa que `failure_risk_v1` reconozca failures que v1.003 no
reconocía?

Imagina dos revisores que miran los mismos expedientes. Uno encuentra algunos
problemas y el otro encuentra otros, con solapamiento parcial. Si el segundo
revisor demuestra que capta casos que el primero pasó por alto, eso es
información adicional, aunque no transforme automáticamente al segundo en confiable.

`failure_risk_v1` hace algo parecido: en los mismos 76 casos de OOS, detecta
más fallos reales que v1.003. Eso es importante analíticamente porque sugiere que
el modelo especializado en riesgo de failure tiene una “mirada” distinta que puede
ser complementaria. Pero no significa que haya llegado a confiabilidad operativa.

La comparación es analítica, no de fusión. No se han unido los modelos todavía.

---

## 15. Ejemplos fáciles

### Continuation

Imagina que subes una cuesta y sigues subiendo. La tendencia continúa.
Eso es `continuation`.

### Reversal

Imagina que, subiendo una cuesta, la calle de repente baja en dirección opuesta.
Eso es `reversal`.

### Failure

Imagina que crees que estás subiendo hacia un mirador, pero te encuentras con que
el camino se detiene o pierde fuerza antes de llegar.
Eso es `failure`.

### failure_anatomy_v1 como médico

Un médico no solo dice “está enfermo”. Pregunta:
- ¿hay fiebre?
- ¿hay tos?
- ¿hay antecedentes?
- ¿hay signos de riesgo?

La línea `failure_anatomy_v1` hace algo similar con las secuencias ICT:
- ¿hay conflicto HTF?
- ¿hay contexto adverso?
- ¿hay ambigüedad direccional?
- ¿hay restricciones contradictorias?
- ¿hay poca madurez de secuencia?

Busca síntomas antes de que ocurra el resultado, con la regla de que nada de
esos síntomas puede conocerse mirando el futuro.

### failure_risk_v1 como detector de riesgo de fallo

`failure_risk_v1` es como un detector de riesgo enfocado, no un diagnóstico
general. No dice qué tendencia seguirá, sino si la secuencia tiene alto riesgo de
no llegar a su resultado esperado.

---

## 16. Resumen de estados

| Línea | Estado |
|-------|--------|
| tf_outcome_v1_001 | BLOCKED/REVIEW |
| tf_outcome_v1_002 | REVIEW |
| tf_outcome_v1_003 | REVIEW |
| failure_anatomy_v1 | READY_FOR_TRAINING_REVIEW (dataset listo) |
| failure_risk_v1 | REVIEW (mejor que v1.003, pero sobreajuste, mala calibración y PR-AUC inferior al baseline) |

---

## 17. Siguiente paso

El siguiente paso lógico es trabajar sobre el modelo ya entrenado:

1. Analizar y mejorar la calibración de `failure_risk_v1`.
2. Comprender y reducir el sobreajuste.
3. Entender por qué la mejora en recall viene con mala precisión-recall.
4. Mantener `can_trade=false`.
5. Evaluar en el futuro una fusión tardía con v1.003, solo si el modelo cierra
   en REVIEW reproducible sin fallos de procedencia.

Hasta entonces:
- `can_trade=false`
- `shadow_mode=true`
- no trading
- no fusionar modelos con v1.003 todavía
- no trading
- no trading

---

*Fin del reporte simple.*