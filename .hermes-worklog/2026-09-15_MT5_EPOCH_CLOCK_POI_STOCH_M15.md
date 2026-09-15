# Cierre de misión — MT5 EPOCH CLOCK / POI+Stoch M15
## MC-20260914-083000-poi-stoch-m15 · 2026-09-15

**Estado del cierre:** documentación entregada, código no tocado en esta sesión, trading/servicio no activados.

---

## Estado inicial

- **Botón de lectura segura:** `Armar bot` estaba disponible en la terminal cuando el adaptador MT5 está conectado, aunque `execution_enabled=false`; el loop registra observaciones y no crea ciclos ni envía órdenes.
- **Evaluador del productor mecánico:** presentaba H1, H6 y H7 parciales del feed canónico. H1/H6 eran lectura observacional, H7 quedaba incompleto porque el motor no publicaba la evidencia causal de sweep en un artefacto cerrado.
- **Misión abierta:** MC-20260914-083000-poi-stoch-m15, plan `.hermes/plans/2026-09-14_POI_STOCH_M15_SIMPLIFICATION.md`. Inventario de bloqueos iniciado, contrato POI+Stoch v1 congelado, reloj MT5 aún por confirmar en la ruta operativa.

---

## Trabajo realizado

- **Corrección H1 (reloj MT5):** el adaptador MT5, `TerminalRuntime` y los launchers dejaron de aplicar el offset visual UTC+3 al campo `time` de la API Python. El epoch UTC se trata como epoch UTC; las velas M15 abiertas, futuras o vencidas son rechazadas por el adaptador y el servicio queda fail-closed. Evidencia: `mc20260914_mt5_clock_verification.py` + tests del adaptador y del servicio.
- **Corrección H6 (estado del feed canónico):** se separó la lectura de la evidencia causal; el feed puede leerse sin pretender que la cadena de sweep/displacement/BOS/CHoCH esté completa cuando no lo está.
- **Desempate de temporalidad:** el v1 exigía `Role.POI` como condición de elegibilidad, pero el motor operativo publica FVG/OB con `Role.REFINEMENT`. El v2 (`CONTRATO_POI_STOCH_M15_V2.md`) elimina `Role.POI` como filtro y adopta criterio alternativo: tipo + temporalidad acordada + estado + símbolo + geometría + disponibilidad temporal. Esto permite que el evaluador funcione sobre el feed operativo real y no solo sobre backtest.
- **Filtro de símbolo:** la evaluación elige POI por `obj.symbol == symbol_evaluado`, lo que evita cruzar estructura de otro par cuando se evalúa EURUSD.
- **Temporalidades acordadas:** D1/H4/H1 como POI-TFs; M15 como TF de ejecución/refinamiento, no como POI primario para esta estrategia simplificada. Esto se documenta en el v2 y en el contrato de cierre propuesto.
- **Lambda — bug identificado en sesión:** en el contexto de esta misión se identificó un problema de lambda en la construcción del gate/lectura del evaluador. No existe artefacto de contrato ni plan con ese nombre como archivo separado; queda como decisión pendiente de verificar y, si corresponde, corregir en la implementación del evaluador.

---

## Estado actual por área

### Completado

- Reloj MT5 corregido y verificado en ruta: epoch UTC sin offset; adaptador y servicio rechazan velas no aptas; launchers sin `+3h`; interfaz declara `Epoch UTC`.
- Estrategia simplificada 문서의 v2 consolidada: elegibilidad sin `Role.POI`, POI-TFs acordadas, estados excluidos, proximidad, estocástico M15 14,3,3, reglas de cruce 20/80, coincidencia de contacto con zona, vigencia, `cross_id` de no reutilización, desempate por distancia y `creation_time`, conflicto de POI opuestas.
- Contrato de cierre propuesto armado: ruta alternativa a Fase 2B que declara explícitamente que no usa probability fabricada ni confirmed legacy, y que define autoridad sobre POI elegible + cruce estocástico M15 vigente + sesión + gates de riesgo.

### En corrección

- `price_type` en el payload de salida del evaluador: el evaluador devuelve `price_type` (`"ASK"`/`"BID"` según dirección) pero la corrección/validación de que el campo refleja realidad del mercado y no un placeholder sigue en revisión.
- `cross_id` de no reutilización: la regla de no reutilización del cruce está definida en el contrato (sección 8.3), pero la implementación/consistencia del registro de `cross_ids` consumidos entre evaluaciones está en corrección.

### Pendiente

- **Contrato operativo:** decisión de adoptar o no la ruta simplificada como operativa. El documento propuesto ya está en `docs/contratos/`, pero no es obligación hasta decisión de Rubén.
- **Interfaz:** la terminal debe poder mostrar el nuevo gate POI+Stoch y no mezclar gates legacy con gates nuevos. Pendiente de implementación/verificación.
- **DEMO/verificación live:** no se inició; bloqueada por política y por decisión.

---

## Decisiones pendientes

- **Operar simplificado vs esperar Fase 2B:** el contrato propuesto documenta la autoridad de una ruta alternativa, pero la decisión de operar queda para Rubén. Fase 2B sigue en `DRAFT_BLOCKED`.
- **Si se decide operar simplificado:** se recomienda verificar `price_type`, `cross_id`, `readiness.ready` como representación limpia de la autoridad nueva, y mantener `can_trade=false` hasta la auditoría D5/CRO y autorización expresiva.
- **Si se decide bloquear:** la misión cierra con la corrección del evaluador y el contrato documentado como evidencia de que existe una estrategia alternativa definida, pero no activada.

---

## Próximo estado

Depende de la decisión de operar o bloquear:

- **Operar:** habilitar el contrato propuesto, verificar `readiness.ready`, UI del gate, y DEMO con contrato explícito antes de cualquier orden.
- **Bloquear:** cerrar la misión como evidencia de que la estrategia simplificada está definida y corregida, pero no activada; conservar el contrato, el evaluador y las correcciones del reloj para una futura decisión.

---

## Invariantes conservados

- `engine/` no importa `backtest/`.
- `can_trade=false` como invariante global salvo autorización explícita.
- Ningún trabajo de esta misión envía órdenes reales ni DEMO sin contrato y autorización explícitos.
- El reloj MT5 queda como misión separada y verificada; no se mezcla con la autoridad de entrada del evaluador.

---

> Cierre documental de MC-20260914-083000-poi-stoch-m15. No se activó trading, no se reinició servicio, no se ejecutó orden de prueba en esta sesión.
