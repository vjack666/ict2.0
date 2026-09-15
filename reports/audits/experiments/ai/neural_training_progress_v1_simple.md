# Reporte Simple — Avance Entrenamiento IA / TensorFlow

**Fecha:** 2026-09-15
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

Por ejemplo, si la red solo adivinara, su acierto sería cercano al nulo o al
nivel de azar. Si “aprendió”, su respuesta es mejor que esa línea de base.

Pero aprender no es lo mismo que ser bueno. Una red puede aprender algo y
aún así cometer muchos errores. Aprender es una señal de progreso, no una
certificación de confiabilidad.

---

## 3. ¿Qué significan `continuation`, `reversal` y `failure`?

La red estudia tres tipos de resultado posible para una secuencia ICT:

- `continuation`: la tendencia sigue caminando en la misma dirección.
  Es como un peatón que sigue cruzando la calle sin detenerse.

- `reversal`: la dirección gira y camina al revés.
  Es como un semáforo que cambia de sentido a mitad del cruce.

- `failure`: la secuencia parecía válida, pero pierde fuerza y no alcanza el
  resultado esperado.
  Es como una señal de tráfico que se ve bien, pero el peatón no logra termina
  r la cruzar como se planeó.

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
   labels a horizonte corto.

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

En palabras simples: la red empezó a captar alguno fallo, pero muy poco.
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
- Drivers candidatos organizizados por taxonomía.

En palabras simples: en lugar de preguntar “¿qué resultado tendrá esta
secuencia?”, se pregunta “¿esta secuencia tiene síntomas que la hacen propensa
a fallar?”. Es como pasar de un diagnóstico general a una revisión médica
más enfocada.

---

## 9. ¿Qué falta para decir que la IA es confiable?

Falta mucho antes de poder confiar en la IA para algo operativo:

1. **Más datos.**
   292 eventos es un comienzo, pero es poco para una red neuronal.

2. **Más fallos en OOS.**
   La clase `failure` necesita más ejemplos fuera de la muestra de entrenamiento.

3. **Reproducción causal completa.**
   Hay que cerrar la verificación FULL/PREFIX desde el productor original.

4. **Calibración.**
   La red no solo debe acertar, tiene que ser honesta sobre cuándo no lo sabe.
   Hay que medir ECE, Brier, curvas de confianza.

5. **Baseline.**
   Hay que comparar la red contra algo simple y ver si realmente aporta algo.

6. **Métricas separadas por split.**
   TRAIN puede engañar. VALIDATION advierte sobre sobreajuste. OOS es la prueba
   final. Todas deben reportarse por separado.

7. **Más experimentos.**
   Una versión no basta. Hay que probar variaciones, mantener límites y
   documentar honestamente.

---

## 10. Ejemplos fáciles

### Continuation
Imagina que subes una cuesta y sigues subiendo. La tendencia continúa.
Eso es `continuation`.

### Reversal
Imagina que subiendo una cuesta, la calle de repente baja en dirección opuesta.
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

---

## 11. ¿Esto autoriza trading, DEMO, live signal o producción?

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

## 12. Resumen de estados

| Línea | Estado |
|-------|--------|
| tf_outcome_v1_001 | BLOCKED/REVIEW |
| tf_outcome_v1_002 | REVIEW |
| tf_outcome_v1_003 | REVIEW |
| failure_anatomy_v1 | READY_FOR_TRAINING_REVIEW |

---

## 13. Siguiente paso

El siguiente paso lógico es entrenar `failure_risk_v1` sobre el dataset
`failure_anatomy_v1`, auditarlo, compararlo contra baseline, y solo después
evaluar una fusión tardía con v1.003.

Hasta entonces:
- `can_trade=false`
- `shadow_mode=true`
- no trading
- no trading
- no trading

---

*Fin del reporte simple.*
