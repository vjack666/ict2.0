# DECISION_CONTRATO_OPERATIVO_BOTON_MECANICO_V1.md

**Archivo:** `docs/planificacion/DECISION_CONTRATO_OPERATIVO_BOTON_MECANICO_V1.md`
**Fecha:** 2026-09-15
**Autoría:** nexus (planificación)
**Ámbito:** criterios para la decisión del usuario sobre el botón del bot mecánico; no contiene autorización de trading ni cambio de config.
**Nota:** documento de criterios, no de ejecución. NO activa órdenes, NO reinicia servicios, NO firma configuración.

---

## 1. Contexto de la decisión

El bot mecánico (`mechanical_bot/`) ya tiene infraestructura de armado/escaneo(lista/verificar campos readiness en SDD_DESKTOP_TERMINAL.md §Addendum V3 y ciclo en SDD_MECHANICAL_MT5_BOT.md §Estados). Queda la pregunta operativa: **¿qué permite el botón antes de Fase 2B?**.

Hay dos caminos claros:

- **Camino A:** operar POI+Stoch como estrategia simplificada, con autoridad propia y muro explícito de probabilidad/confirmed.
- **Camino B:** bloquear until Fase 2B, manteniendo can_trade=false global y limitando el botón a escaneo/armado sin ejecución.

El usuario decide. nexus no decide.

---

## 2. Qué dice la autoridad existente

### 2.1 SDD_MECHANICAL_MT5_BOT.md §Entrada

- Modo automático exige snapshot con `probability >= 0.70` y `confirmed`.
- Líneas relevantes: §Entrada (tabla BUY/SELL probabilidad >= 0.70) y §Verificación/Integración del terminal local ("snapshot exige símbolo, confirmación booleana estricta, probabilidad finita dentro de [0,1]...").

**Implicación directa:** si se deja el modo automático bajo ese contrato, el Camino A **no es compatible** sin modificar este SDD o el adaptador de entrada.

### 2.2 SDD_DESKTOP_TERMINAL.md §Addendum V3

- `readiness.ready` exige simultáneamente: `execution_enabled=true`, snapshot canónico válido con antigüedad máx 20 min, dirección BUY/SELL, probabilidad finita `>=0.70`, `confirmed=true`, cruce estocástico M15 direccional, sesión Londres/NY.
- Líneas relevantes: Addendum V3, párrafos de `readiness.ready`.

**Implicación directa:** el contrato de readiness actual también exige probabilidad+confirmed. Sin ajuste, el Camino A no puede publicar `readiness.ready=true` bajo esa definición.

### 2.3 CONTRATO_POI_STOCH_M15_V2.md §11

- La salida del evaluador es `ENTRY_VALID` o un status de rechazo explícito.
- **No incluye** `probability` ni `confirmed` en la salida del evaluador (ver §11, campos y §11.2).
- El evaluador es la base lógica del Camino A: POI elegible + cruce M15 vigente + gates de riesgo.

**Implicación directa:** el Camino A es coherente con el contrato de estrategia simplificada, pero incompatibile con el contrato de entrada actual del bot mecánico **si** el bot usa `probability >= 0.70` y `confirmed` como última autoridad para ejecutar.

### 2.4 SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md §4-5

- Fase 2B está `DRAFT_BLOCKED`; publicación atómica del snapshot de señal bloqueada hasta gates (`direction_rule`, `confirmation`, `calibration`, `abstention_ood`, `costs_fill`, `causality`, `provenance`, `edge`, `production_authorization`).
- §4 define los requisitos del certificado de calibración (probabilidad finita, fit/validation/OOS, Brier, curva de fiabilidad).
- §5: invariantes `engine.can_trade=false`, `entry_authorized=false`, Fase 2B requiere preregistro, auditoría D5 y gates de datos/calibración/edge.

**Implicación directa:** es la base del Camino B. Hasta que esos gates no pasen, el productor no puede publicar una señal operable certificada.

---

## 3. Camino A — Operar POI+Stoch como estrategia simplificada

### 3.1 Resumen

El botón activa y ejecuta usando el evaluador POI+Stoch como **autoridad operativa propia**, con reglas explícitas y muro explícito que rechaza cualquier inyección de `probability` o `confirmed` externo.

### 3.2 Autoridad del Camino A

Compuesta por:

1. POI elegible: `ObjectType.FVG/ORDER_BLOCK`, `origin_tf` en D1/H4/H1, estado `ACTIVE` o `PARTIALLY_MITIGATED`, geometría válida, symbol coincidente, `tradable_time <= decision_time`, dirección ±1. (CONTRATO_POI_STOCH_M15_V2.md §2.1.)
2. Cruce estocástico M15 vigente: 20/80, `cross_type` coherente con POI, `cross_id` no consumido, verificable. (CONTRATO_POI_STOCH_M15_V2.md §5-8.)
3. Sesión Londres/NY activa. (SDD_MECHANICAL_MT5_BOT.md §Verificación; SDD_DESKTOP_TERMINAL.md §Addendum V3.)
4. Gates de riesgo: ciclo + posición. (SDD_MECHANICAL_MT5_BOT.md §Ciclo y riesgo; CONTRATO_POI_STOCH_M15_V2.md §10.)
5. Sin `probability` fabricada ni `confirmed` legacy. La autoridad es el evaluador, no un snapshot probabilístico externo.

### 3.3 Requisito clave de readiness

Bajo Camino A, `readiness.ready` se redefine para ser **autoridad real del evaluador**, no cumplimiento del Addendum V3 actual:

- `readiness.ready` = `status == ENTRY_VALID` **y** los gates de sesión y ciclo pasan, **sin** exigir probabilidad numérica ni `confirmed=true` externo.
- El muro debe ser explícito: la capa de ejecución rechaza snapshots que lleven `probability` o `confirmed` exigidos por el SDD actual.

### 3.4 Qué cambia en código, tests, UI, autoridad

**Código:**

- Capa de entrada del bot debe aceptar la salida del evaluador como señal válida, NO un snapshot con probabilidad/confirmed. Esto es un cambio en la autoridad de entrada y debe estar en el hilo del cambio.
- Posible ajuste del muro de `readiness.ready` o de la ruta de `latest_snapshot.json` vs `signal_assessment`, dependiendo de cómo se implemente sin romper el contrato de terminal.
- El productor de señal Fase 2A/2B **no** se activa con esto; el Camino A es distinto y explícitamente separado.

**Tests:**

- Nuevos tests de la ruta evaluador→bot: confirmar que `ENTRY_VALID` activa el ciclo, que `NO_CROSS`, `CROSS_EXPIRED`, `CYCLE_ACTIVE_SAME_DIRECTION`, `NO_ELIGIBLE_POI_NEAR_PRICE` lo bloquean.
- Tests de muro: confirmar que snapshot con `probability/confirmed` no inyecta autoridad si no hay `ENTRY_VALID`.
- No se tocan los tests de caja negra actuales sin contrato; el riesgo de prueba está en la nueva ruta.

**UI:**

- El panel debe mostrar que el botón está bajo “estrategia simplificada POI+Stoch”, no bajo “productor de señal Fase 2B”.
- Debe mostrar la causa de `readiness` explícitamente: POI, cruce, sesión, ciclo.
- Conflicto: SDD_DESKTOP_TERMINAL.md Addendum V3 habla de readiness con probabilidad+confirmed. La UI debe estar sincronizada con la autoridad real, o bien el SDD de terminal se actualiza para aclarar que existen dos modos de readiness con autoridad diferente.

**Autoridad:**

- El motor inteligente sigue conservando `can_trade=false`. Esto es explícito y no cambia con Camino A.
- El botón opera bajo contrato de estrategia simplificada, no bajo productor Fase 2B.
- La separación es crítica: no mezclar autoridad del evaluador POI+Stoch con la autoridad del productor de señal.

---

## 4. Camino B — Bloquear hasta Fase 2B

### 4.1 Resumen

El botón sigue existiendo, pero solo permite armado/escaneo/listado; `can_trade` global y la autoridad de ejecución siguen bloqueados hasta que Fase 2B esté completa.

### 4.2 Autoridad del Camino B

- `engine.can_trade=false` y `entry_authorized=false` se mantienen. (SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md §5.)
- El botón no ejecuta. Puede mostrar evaluación, evidencia diagnóstica, estado del cycle, pero sin enviar orden.
- La ejecución real espera al contrato del productor Fase 2B.

### 4.3 Requisito para desbloquear Fase 2B

Según SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md §4-5, faltan:

1. **Preregistro económico:** estado actual `DRAFT_BLOCKED / NO EJECUTAR` hasta que provenance, reproducibilidad, costes/fill, horizonte, potencia/estabilidad y autorización tengan `PASS`.
2. **Auditoría D5:** la auditoría independiente tiene que validar antes de publicación.
3. **Gates de datos:** contrato de datos, decisión temporal, rechazo de feed inválido.
4. **Gates de calibración:** regla direccional, definición causal de `confirmed` (distinta del estocástico final del bot), método calibrado de probabilidad con train/validation/OOS, Brier, curva de fiabilidad. `score_to_probability()` no es sustituto.
5. **Gates de edge y autorización:** antes de cualquier promoción.
6. **Cadena determinista congelada** que incluya FULL/PREFIX, determinismo, fixtures adversariales, bitácora hash.

Hasta que eso pase, el productor no puede publicar el snapshot atómico con `symbol/direction/probability/confirmed/asof_time`.

### 4.4 Qué cambia en código, tests, UI, autoridad

**Código:**

- Prácticamente nada de ejecución. Posible añadir/unstickear documentación de “qué falta para Fase 2B” en el panel o en la bitácora.
- No se modifica la capa de entrada del bot para aceptar probabilidad/confirmed.

**Tests:**

- Se pueden añadir tests de la ruta “botón bloqueado”: confirmar que el armado no produce ciclo ni order_send.
- No se abre la ruta de ejecución POI+Stoch.

**UI:**

- El panel debe ser claro: “modo escaneo/armado, ejecución bloqueada hasta Fase 2B”.
- No debe sugerir que `readiness.ready` calza con ejecución.

**Autoridad:**

- Se mantiene el contrato vigente sin modificar: SDD_MECHANICAL_MT5_BOT.md, SDD_DESKTOP_TERMINAL.md, productor Fase 2B.
- No hay autoridad nueva ni muro nuevo.

---

## 5. Comparación de implicaciones

| Dimensión | Camino A | Camino B |
|---|---|---|
| Autoridad de ejecución | Evaluador POI+Stoch; muro explícito contra probability/confirmed externo | Ninguna hasta Fase 2B; productor DRAFT_BLOCKED |
| Modifica SDD_MECHANICAL_MT5_BOT.md §Entrada | Sí, o la ruta de entrada del bot debe vivir bajo contrato distinto | No necesariamente; o sí solo para dejar explícito el bloqueo |
| Modifica SDD_DESKTOP_TERMINAL.md §Addendum V3 | Sí, `readiness.ready` debe homicicar autoridad real vs probabilidad+confirmed | No obligatoriamente, salvo para aclarar que el botón está bloqueado |
| Usa CONTRATO_POI_STOCH_M15_V2.md §11 como base | Sí, directamente | No como autoridad de ejecución |
| Usa SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md §4-5 como base | No; es contrato distinto | Sí, explícitamente |
| Tests nuevos | Ruta evaluador→bot, muros, bloqueos | Ruta “armado sin ejecución” |
| UI | Debe declarar autoridad y modo “estrategia simplificada” | Debe declarar “bloqueado hasta Fase 2B” |
| Riesgo principal | Incompatibilidad contractual con SDD actual si no se documenta/ajusta el muro | Fase 2B tarda; el botón queda limitado |
| Riesgo secundario | Que se mezcle autoridad del evaluador con authority del productor y se pierda trazabilidad | Que el bloqueo se perciba como parálisis en vez de contrato vigente |

---

## 6. Recomendación de criterios (para que el usuario decida)

### 6.1 Si el usuario quiere probar el botón en DEMO ahora

Camino A puede ser razonable si:

- El usuario acepta explícitamente que esto es “estrategia simplificada POI+Stoch”, no productor Fase 2B.
- Se acuerda un **documento de límites DEMO ≠ producción**: cuenta DEMO, bloqueo de envío si cambia la cuenta/tipo, límites de ciclo, y registro de caja negra.
- Se decide qué hace con la autoridad actual de entrada (`probability >= 0.70` + `confirmed`) y con el Addendum V3: se modifica, se aclara, o se deja un muro explícito que el modo simplificado no calza con readiness actual.
- Se hace commit selectivo solo de lo realmente necesario: la ruta de ejecución POI+Stoch, tests de esa ruta, y UI/origen de autoridad. No se ensucia Fase 2B ni el productor con esto.
- Se conserva `engine.can_trade=false` y la separación del motor inteligente.

### 6.2 Si el usuario prefiere esperar evidencia científica

Camino B es el que conserva el contrato actual intacto:

- Se mantiene `can_trade=false` global.
- El botón permite escaneo/armado sin ejecución.
- Se documenta qué falta para Fase 2B (preregistro, auditoría D5, gates de datos/calibración/edge).
- No se abre la ruta de ejecución POI+Stoch hasta que haya contrato propio y verificación.
- Se evita la incompatibilidad contractual con SDD_MECHANICAL_MT5_BOT.md §Entrada y SDD_DESKTOP_TERMINAL.md §Addendum V3.

---

## 7. Riesgos generales de la decisión

**Riesgo del Camino A:**

- Confusión de autoridad: ejecutar bajo POI+Stoch pero presentarlo como si fuera señal del productor Fase 2B (o viceversa).
- Incompatibilidad contractual silenciosa con SDD_MECHANICAL_MT5_BOT.md §Entrada y §Addendum V3 si no se aclara el muro de probabilidad/confirmed.
- Riesgo de testing insuficiente de la nueva ruta evaluador→bot.
- Riesgo de que el usuario confunda “DEMO” con “listo para producción”.

**Riesgo del Camino B:**

- Bloqueo prolongado si Fase 2B tarda más de lo esperado.
- El botón puede volverse percibido como inútil en DEMO si no se explica bien que está en modo escaneo/armado.
- Riesgo de que la evidencia de Fase 2B nunca llegue con los gates solicitados.

**Riesgo común:**

- Sin documento claro, el stakeholders mezcla los dos contratos y pierde trazabilidad.
- Sin límites DEMO bien definidos, cualquier prueba puede correrse de rango.

---

## 8. Petición al usuario

Esta decisión pide al usuario que diga, explícitamente:

1. ¿Cuál camino prefiere?
2. Si Camino A:
   - ¿Acepta documento de límites DEMO ≠ producción?
   - ¿Quién decide/acompaña el ajuste de autoridad de entrada del bot y de readiness (SDD_MECHANICAL_MT5_BOT.md §Entrada, SDD_DESKTOP_TERMINAL.md §Addendum V3)?
   - ¿Qué scope de cambio es aceptable para el commit selectivo?
3. Si Camino B:
   - ¿Debe quedar explícito en la UI/estado que el botón está bloqueado hasta Fase 2B?
   - ¿Se desea un checklist público de lo que falta para Fase 2B?

---

## 9. Lo que NO está en este documento

- No activa órdenes.
- No reinicia servicios.
- No firmar cambios en configuración de ejecución.
- No decide por el usuario.
- No certifica Fase 2B ni la eligibilidad real de POI en tiempo real.

---

## 10. Archivos de referencia de esta decisión

- `docs/tesis/SDD_MECHANICAL_MT5_BOT.md`
- `docs/tesis/SDD_DESKTOP_TERMINAL.md`
- `docs/contratos/CONTRATO_POI_STOCH_M15_V2.md`
- `docs/tesis/SDD_MECHANICAL_SIGNAL_PRODUCER_V1.md`
- `docs/planificacion/DECISION_CONTRATO_OPERATIVO_BOTON_MECANICO_V1.md` (este)

---

*Documento de criterios. Listo para que el usuario decida.*
