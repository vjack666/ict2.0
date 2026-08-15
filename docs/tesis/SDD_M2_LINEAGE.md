# SDD_M2_LINEAGE.md — Piloto SDD: Trazabilidad Causal Emitida del Motor

**Estado:** SUPERSEDED (el código ya implementa `event_objects`; ver nota 2026-08-14)
**Autoridad:** spec de diseño de estrategia (cadena SDD_GOVERNANCE.md §0 #7)
**Dominio:** Forex / ICT-SMC exclusivo. Prohibido: binarias, QUOTEX, OTC, indicadores (ATR/RSI/EMA).
**Motor afectado:** `engine/sequence.py` + nuevo módulo `engine/lineage.py` (consumidor puro)
**No toca:** LTF estratégico, Macro/News, WR/PF, EDGE, reglas de entrada, gestión de riesgo.

---

## 1. POR QUÉ EXISTE (relación con tesis)

HYP-002 (Fase 5/6) demostró que el motor ya crea `MarketObject` con `id` + `parent_object`
para SWEEP/DISPLACE/BOS/POI/REFINEMENT/RETURN y los emite en `signal["event_ids"]`. Pero:

- El grafo real de objetos (`state.event_objs`: id → MarketObject con su `parent_object`)
  se construye y **nunca se emite ni es consultable** desde fuera del motor. La señal solo
  lleva un mapa plano `event_ids` (strings), perdiendo la topología `parent_object`.
- No existe API pública que demuestre post-hoc que la cadena
  `LIQUIDITY→SWEEP→DISPLACE→BOS→POI/REFINEMENT→RETURN` está enlazada por **origen**
  (`parent_object`), y no meramente por proximidad temporal (el anti-patrón que SDD_GOVERNANCE §8
  prohíbe explícitamente).
- Hay código muerto/defectuoso en `engine/sequence.py:847-849`:
  `if sigs: print("primera:", sigs[0])` — `sigs` no está definido (el impl devuelve `signals`);
  es un `print` fugado en un módulo de librería (viola "sin salida de debug silenciosa").

Esto impide al Auditor Independiente verificar la dimensión CAUSALITY de SDD_GOVERNANCE §4
sobre el producto real, no solo sobre scripts de validación en `research/`.

Tesis de respaldo: `docs/ict/SPEC_TESIS_FORMAL.md` (lectura causal ICT/SMC) +
`research/hypotheses/HYP-002/INFO_LOSS_AUDIT.md` (Opción A: el motor debe producir y
conservar el linaje causal como grafo de objetos con id+parent).

---

## 2. QUÉ DEBE HACER (comportamiento esperado)

1. **Eliminar** el bloque muerto `if sigs: print("primera:", sigs[0])` al final de
   `engine/sequence.py` (líneas 847-849). No altera ninguna salida ni firma.
2. **Emitir** el grafo de objetos: en `run_sequence_traced` (y en la señal construida dentro de
   `_run_sequence_impl`), añadir `"event_objects": dict[id -> MarketObject.to_dict()]` al dict de
   señal, poblado desde `state.event_objs` en el instante de la señal (snapshot inmutable de la
   cadena ya confirmada). Aditivo: no cambia `run_sequence` (2-tuple legacy).
3. **Crear** `engine/lineage.py` con una función pura `trace_setup_lineage(signal: dict) -> dict`
   que, dado un `signal` con `event_ids` + `event_objects`, reconstruye la cadena causal:
   - resuelve cada `parent_object` a su objeto real;
   - verifica que `parent.bar_index <= child.bar_index` (anti look-ahead por origen);
   - devuelve `{linked: bool, chain: [ids en orden LIQUIDITY→...→RETURN], breaks: [...]}`.
   Es CONSUMIDOR PURO del motor (no importa nada de `ict_backtest/`, no decide).

---

## 3. QUÉ NO DEBE HACER (límites)

- No cambiar ninguna regla ICT/SMC (sweep/displacement/BOS/entry/zone).
- No introducir indicadores (ATR/RSI/EMA/MACD/Bollinger). El nivel ya es OHLC-derivable.
- No alterar la firma de `run_sequence` (2-tuple). Solo `run_sequence_traced` gana el campo.
- No cambiar WR/PF/R, LTF, Macro/News ni edge.
- No tocar `ict_backtest/` (Ley: el backtest es consumidor puro).
- No inferir linaje por proximidad temporal: el `trace` DEBE usar `parent_object` declarado.

---

## 4. ENTRADAS / SALIDAS / INVARIANTES

**Entradas:** `signal` dict (ya emitido por `run_sequence_traced`) con claves
`event_ids` (mapa de rol→id) y `event_objects` (mapa id→dict de MarketObject).

**Salidas:** `trace_setup_lineage` → dict:
```
{
  "linked": bool,            # toda la cadena enlazada por parent_object
  "chain": [id, ...],        # orden LIQUIDITY→SWEEP→DISPLACE→BOS→POI/REFINEMENT→RETURN
  "breaks": [str, ...],      # descripción de cada eslabón roto
  "parent_resolved": bool,   # todo parent_object apunta a id existente
  "temporal_ok": bool,       # parent.bar_index <= child.bar_index para todo eslabón
}
```

**Invariantes:**
- `engine/lineage.py` NUNCA importa `ict_backtest/`.
- `MarketObject.to_dict()` ya existe (market_object.py) — se reusa, no se modifica el modelo.
- `event_objects` es snapshot en el instante de señal (los objetos ya tienen `parent_object`).

---

## 5. CASOS NEGATIVOS / DATO FALTANTE

- `signal` sin `event_objects` → `trace_setup_lineage` devuelve `linked=False`,
  `breaks=["event_objects ausente"]`, sin lanzar (comportamiento UNKNOWN documentado, no fail-open).
- `parent_object` que apunta a id inexistente → `parent_resolved=False`, `breaks` lo lista.
- `bar_index` futuro en un padre → `temporal_ok=False` (jamás debe ocurrir; es red de seguridad).

---

## 6. CRITERIOS DE FALSACIÓN

El linaje se demuestra ROTO si, en una señal real del motor, `trace_setup_lineage` devuelve
`linked=False` cuando la secuencia sí completó todos los eventos (es decir: los ids existen pero
no están enlazados por `parent_object`). Eso probaría que el motor infiere por proximidad, no
por origen — falsando SDD_GOVERNANCE §8. (Hipótesis de trabajo: con el código Fase 5/6 actual,
`linked` debe ser `True` en señales completas; el piloto lo confirma con test.)

---

## 7. CRITERIOS DE ACEPTACIÓN

1. `python -m py_compile engine/sequence.py engine/lineage.py` limpio.
2. El bloque muerto `if sigs: print(...)` desaparece de `engine/sequence.py` (grep lo confirma).
3. `run_sequence_traced(...)` en señal completa incluye `"event_objects"` no vacío con 7 objetos.
4. `trace_setup_lineage(signal)` sobre señal completa devuelve `linked=True`, `parent_resolved=True`,
   `temporal_ok=True`, `chain` en orden LIQUIDITY→SWEEP→DISPLACE→BOS→(POI)→REFINEMENT→RETURN.
5. Tests unitarios nuevos pasan; `tests/test_a1_topdown_filter.py` y `tests/test_b2_funnel.py`
   (que usan `run_sequence`) siguen verdes (no toco la firma 2-tuple).
6. Verificación semántica (§4 SDD): IDENTITY (ids únicos), LINK (parent resoluble+anterior),
   CAUSALITY (parent declarado == id real), ORDEN (sweep<disp<bos<entry) — todos OK en señal real.

---

## 8. IMPACTO / TRAZABILIDAD

- **Módulos afectados:** `engine/sequence.py` (elimina código muerto + emite `event_objects`),
  nuevo `engine/lineage.py` (consumidor puro).
- **Tests afectados:** nuevos `tests/test_m2_lineage.py`. Tests existentes de `run_sequence`
  NO afectados (firma legacy intacta).
- **Auditorías afectadas:** SDD_GOVERNANCE §4 (causalidad) ahora verificable sobre producto real.
- **Resultados históricos:** NINGUNO obsoleto (no cambia semántica de trading; es REPRESENTACIÓN/
  TRAZABILIDAD pura). Sin regresión semántica.
- **Requisito modificado:** ninguno de la tesis; se CIERRA un GAP de trazabilidad ya diagnosticado
  en HYP-002 (INFO_LOSS_AUDIT.md Opción A), sin alterar la estrategia.

---

## 9. DEFINITION OF READY (checklist SDD_GOVERNANCE §1)

| # | Check | Estado |
|---|-------|--------|
| 1 | Objetivo claro | ✅ §1 — emitir/conectar linaje causal ya construido |
| 2 | Relación con tesis | ✅ SPEC_TESIS_FORMAL + HYP-002 INFO_LOSS_AUDIT (Opción A) |
| 3 | Comportamiento esperado | ✅ §2 (eliminar muerto + emitir grafo + trace puro) |
| 4 | Entradas | ✅ §4 (signal con event_ids+event_objects) |
| 5 | Salidas | ✅ §4 (dict linked/chain/breaks/parent_resolved/temporal_ok) |
| 6 | Invariantes | ✅ §4 (lineage no importa ict_backtest; to_dict reusado) |
| 7 | Límites | ✅ §3 (no ICT rules, no indicadores, no firma 2-tuple, no LTF/edge) |
| 8 | Casos negativos | ✅ §5 (sin event_objects / parent roto / bar_index futuro) |
| 9 | Dato faltante | ✅ §5 (UNKNOWN documentado, sin fail-open) |
| 10 | Falsación | ✅ §6 (linked=False en señal completa = falsa la §8) |
| 11 | Aceptación | ✅ §7 (py_compile, grep, traced signal, tests) |
| 12 | Impacto | ✅ §8 (sequence + lineage; tests existentes intactos) |
| 13 | Prohibiciones | ✅ §3 (sin ATR/RSI/EMA; sin Macro/LTF/WR/PF/edge; sin QUOTEX/OTC) |

**Veredicto DoR:** READY. Cumple las 13 condiciones. Puede pasar a IMPLEMENTING.

---

## 10. CICLO SDD PREVISTO

DRAFT (este doc) → READY (DoR §9) → IMPLEMENTING (engine/sequence.py + engine/lineage.py)
→ TESTED (tests/test_m2_lineage.py) → SEMANTICALLY_VERIFIED (§4 dims) → AUDITED
(Auditor Independiente: trazabilidad + veto PROMOCIÓN si cambia semántica) → ACCEPTED (Director).

**Estado final (2026-08-14): SUPERSEDED.** El piloto cumplió su objetivo: el motor ya
emite `event_objects` / `event_ids` / `parent_event_id` en `run_sequence_traced`
(engine/sequence.py:1065+; engine/lineage.py consumidor puro). FASE A (2026-08-13) lo
demostró con 18 setups de linaje íntegro, y el FIX de MarketReplay (commit `1651bdf`)
confirmó que el consumidor replay también recibe linaje completo al cablear las
autoridades del engine. No se requiere re-ejecutar la implementación; solo se cierra
el spec como SUPERSEDED porque el código lo superó. Referencia:
`docs/auditoria_market_replay_2026-08-14.md` (auditoría de Codex).
