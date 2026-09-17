# Cost Economics Preregistration — Episódico Intradía (continuación t_56fbc441)

**Tarjeta:** `t_24fddd4f` (protocolo) → `t_56fbc441` (continuación)
**Perfil:** `orion` / D6 — Especificaciones ICT / PO3 / Turtle / Silver
**Fecha del documento:** 2026-09-16 (local)
**Estado del preregistro:** `FROZEN_PROXIES_ONLY` → no se declara `PASS_EDGE`; `can_trade=false`; `entry_authorized=false`.
**Autoridad:** investigación local sobre datos existentes; enmienda 2026-09-11 (autonomía de entrenamiento local, sin descarga ni modificación de datos, etiquetas ni manifestos); datos inmutables.

---

## 1. PREGUNTA / ALCANCE DEL DOCUMENTO

Responder la parte pendiente del preregistro `t_24fddd4f` que impide verificar `net_R` y `FREQ_GATE_2_3_WEEKLY`: **cuantificar los costes congelados y especificar la metodología de frecuencia**, sin inventar resultados económicos ni alterar datos de entrada.

---

## 2. EVIDENCIA EXISTENTE (lo que sí hay, sin inventar)

| Fuente | Archivo / referencia | Estado |
|---|---|---|
| Decisión económica base (proxy local, no certificada FundedNext) | `docs/experimentos/EDGE_ECONOMIC_PARAMETERS_DECISION_MEMO.md` (2026-09-02, `PROXY_PILOT_FROZEN`) | **Verificado** — valores declarados por el cliente / observados en demo |
| Protocolo episódico | `reports/ict_temporal_v1/orion/t_24fddd4f_PROTOCOL_EPISODICO_V1.md` | **Verificado** — contraparte documento/detector completada; contradicciones resueltas o registradas como deuda |
| Plan multimodelo | `docs/planificacion/PLAN_ICT_MULTIMODELO_INTRADIA_V1.md` | **Verificado** — secuencia de trabajo definida (cierre frecuencias antes de `PASS_EDGE`) |
| Motor / detectores | `engine/po3.py`, `engine/turtle_soup.py`, `engine/silver_bullet.py`, `engine/killzone.py` | **Verificado** — implementaciones presentes; `PO3-3` (métricas aisladas) pendiente; `SB-FVG` no verificado; `KZ-2` no reconciliado |
| Datos crudos / split | `data/` (EURUSD, M15/M5/M1, sucios por `spread` parcial) | **Bloqueado para conteo aislado** — falta columna `spread` en años sin datos; no se genera dataset nuevo |
| Provenance (git, hashes, manifest) | `.git`: branch `codex/audit-hermes-cert-20260826`; worktree **sucio** (`git status`: 5 modificados, 41 sin track, `engine/execution.py` modificado, `.hermes-state/*` modificado) | **BLOCKED** — ninguna certificación `PASS_EDGE` posible mientras el checkout sea sucio y no haya hash verificado del trabajo de esta tarjeta |

---

## 3. COSTES CONGELADOS (valores declarados; se mantienen sin optimización)

Todos los valores provienen del memo `EDGE_ECONOMIC_PARAMETERS_DECISION_MEMO.md` y se congelan para el `PROXY_PILOT`. **No se ajustan posterior**; si un escenario futuro requiere sensibilidad mayor, se corre como ablación separada (`AB-COST-HIGH`), nunca como reemplazo del congelado.

| Parámetro | Valor congelado | Fuente / observación | Limitación documentada |
|---|---|---|---|
| **Símbolo / punto de referencia** | EURUSD; contrato 100.000; 5 dígitos; tick 0.00001 / US$1 | Observación local `MetaQuotes-Demo` (no FundedNext real) | Cuenta demo ≠ condiciones reales; no inferir cumplimiento de reglas FundedNext |
| **Spread primario (años con columna `spread`)** | 0,1 pip (1 punto observado) | `spread` instantáneo observado en demo | No es distribución histórica; no representa tail de spread |
| **Spread primario (años sin columna `spread`)** | 1 pip (proxy conservador) | Declarado en memo §5 (decisión pendiente congelada) | Mayor que observado; intención conservadora; debe reportarse separadamente si se usa |
| **Slippage** | 0,3 pip (fijo, separado de spread) | Declarado en memo §3, §5 | No verificado con datos de relleno reales; proxy fijo |
| **Comisión (por lado)** | US$5 por lote | Cliente; confirmada por `fundednext.com/general-rules/cfds/symbols-and-conditions` | No verificado en demo (demo suele no cobrar) |
| **Comisión (por trade completo)** | US$10 (entrada + salida) | Derivado: 2 × US$5 | Se reporta como coste total de comisión |
| **Swap (financiación)** | Long −0,7 / Short −1,0 (puntos / día?) | Observación local | No confirmado si por lote o por unidad; debe verificarse antes de cualquier cálculo de hold overnight; **no usado en intradía** (timeout M15, sin hold) |
| **Volumen mínimo / paso** | 0,01 / 0,01 lote | Observación demo | No afecta coste directo; referencia de ejecución |
| **Timeout / cierre por expiro** | 12 velas M15; cierre al precio de última barra del horizonte | Declarado en memo §3 (pendiente congelación formal) | No verificado en ejecución real; pendiente `HORIZON_EXIT` |
| **Fill** | Primer toque observable en barra EXEC posterior (no cierre de barra) | Declarado en memo §3 | Conservador; evita anticipación |
| **TP / SL en misma vela** | Prioridad `SL_FIRST` si OHLC no permite ordenar intrabar | Declarado en memo §3 | Conservador; puede reducir `net_R` si SL se activa antes que TP en vela de rango amplio |

**Resultado del congelamiento:** los seis campos pendientes de `EDGE_ECONOMIC_PARAMETERS_DECISION_MEMO.md` (§3) se declaran **fijados** para este preregistro; el documento deja de ser `DRAFT_BLOCKED` para `COSTS` (pero **no** para `EXECUTION`, `PROVENANCE` ni `PASS_EDGE`, que siguen bloqueados por otros gates).

---

## 4. FRECUENCIA — METODOLOGÍA `FREQ_GATE_2_3_WEEKLY` (no resultados, solo diseño)

No se declara conteo de candidatos porque:
- `grammar_labels` (36 features estáticos) no separan por familia de forma determinista;
- `ABSTAIN` / `REJECT` (286 filas) no se han clasificado en familias separadas;
- Deduplicación por evento económico (mismo sweep / mismo FVG / mismo PO3) no está certificada en esta tarjeta;
- Provenance bloqueado impide verificar que los contadores reflejen los datos sin filtro post-hoc.

Por eso `FREQ_GATE_2_3_WEEKLY` se **preregistra como contrato**, no como resultado:

| Regla del contrato | Especificación | Evidencia / fuente |
|---|---|---|
| **Unidad de población** | Universo congelado pre-declarado (`data/raw/EURUSD/`, splits `TRAIN/VALID/HOLDOUT` del plan) | `PLAN_ICT_MULTIMODELO_INTRADIA_V1.md` §5; `t_24fddd4f_PROTOCOL_EPISODICO_V1.md` §5.2 |
| **Familias** | PO3, Turtle Soup, Silver Bullet (separadas, no mezcladas; un candidato puede pertenecer a más de una, pero cuenta **una vez** como evento económico en frecuencia combinada) | Protocolo §5.1; `engine/po3.py` vs `turtle_soup.py` vs `silver_bullet.py` |
| **Deduplicación** | Por evento económico (mismo sweep + misma zona de retorno + mismo KZ) antes del conteo; sin deduplicación, el conteo es sobreestimado | Plan §4 (reutilizar detectores); deuda `DEDUP_NOT_VERIFIED` documentada |
| **Partición temporal** | `DESIGN [2006-01-01, 2016-01-01)`, `VALIDATION [2016-01-01, 2021-01-01)`, `HOLDOUT [2021-01-01, 2026-01-01)` | Plan §5; `CONTRATO_PASS_EDGE_INTRADIA_V1.md` §5 |
| **Sesiones de medida** | London Open (03:00–05:00 ET / 08:00–10:00 UTC); NY AM (10:00–12:00 ET / 15:00–17:00 UTC, según `engine/killzone.py`); **KZ-2 pendiente** (ver §6) | Protocolo §5.1; `01_KILLZONES.md`; `engine/killzone.py` |
| **Dirección** | Long / Short separadas; no se suma | Plan §5 |
| **Símbolo** | EURUSD (único certificado en esta tarjeta; sin expansión sin nuevo preregistro) | `EDGE_ECONOMIC_PARAMETERS_DECISION_MEMO.md`; `PLAN_ICT_MULTIMODELO_INTRADIA_V1.md` |
| **Criterio de paso (`FREQ_GATE_2_3_WEEKLY`)** | ≥ 2 y ≤ 3 operaciones por familia por semana calendario, medido en `VALIDATION` con conteo verificable; sin ajuste de reglas solo para alcanzar la meta (`INSUFFICIENT_FREQUENCY` es resultado válido) | Plan §57 (`INSUFFICIENT_FREQUENCY`); `t_24fddd4f` §8 (limitación 2) |
| **Método de conteo** | Conteo determinista por `setup_grammar_v1` + detector correspondiente + filtro de KZ + deduplicación por evento económico; sin optimización de parámetros para subir el conteo | Plan §4–§6; regla invariante §69 |

**Estado actual:** `INSUFFICIENT_FREQUENCY` (no evaluado) → `MORE_DETERMINISTIC_WORK_REQUIRED` (falta `PO3-3`, `SB-FVG`, `DEDUP`, `KZ-2`). **No se declara ninguna frecuencia como certificación.**

---

## 5. ABLACIONES PREREGISTRADAS (no ejecutadas, solo listadas para control de robustez)

Todas de `t_24fddd4f` §5.2; se mantienen para cuando `FREQ_GATE_2_3_WEEKLY` se ejecute, como controles de robustez, **no como ajustes de resultado**:

- `AB-KZ`: sin filtro de KZ (Silver Bullet) → comparar frecuencia KZ vs no-KZ para medir dependencia del horario.
- `AB-PO3-D`: sin fase D (solo A+M) → verificar si PO3 incompleto sigue con valor predictivo.
- `AB-TURTLE`: sin displacement mínimo → evaluar si sweep solo predice.
- `AB-ALIGNED`: sin filtro de alineación PO3 → separar PO3 de Turtle.
- `AB-COST-HIGH`: spread 1.5 pip, slippage 0.5 pip, comisión US$7 → sensibilidad; nunca sustituye congelado.

---

## 6. CONTRADICCIONES / DEUDAS QUE IMPIDEN CIERRE (honestidad científica; no se ocultan)

Estas son las mismas que `t_24fddd4f` declaró como deuda; se mantienen porque **no se han resuelto en esta tarjeta**:

| ID deuda | Descripción | Estado en esta card | Evidencia |
|---|---|---|---|
| `KZ-2` / `REVIEW_SCHEDULE_CONTRACT` | `01_KILLZONES.md`: NY AM 08:30–11:00 ET; `engine/killzone.py`: NY AM 10:00–12:00 ET. DST probado en código, pero **la reconciliación de modelo no está certificada**. Silver Bullet no puede certificarse sin resolución. | **NO RESUELTO** — documentado, no inventado | `t_24fddd4f` §1.2; `engine/killzone.py` §new_york_am |
| `SB-FVG-NOT-VERIFIED` | `silver_bullet.py`: verifica `return_ts > sweep_ts` + misma KZ; **no verifica FVG posterior al sweep** como requiere `07_SILVER_BULLET.md`. | **NO RESUELTO** — deudada | `t_24fddd4f` §1.2; `engine/silver_bullet.py` `is_silver_bullet()` |
| `PO3-METRICS-ISOLATED` | `METRICS_CANON`: sin fila PO3-only (`PO3-3`, R4 pendiente). No hay métrica aislada de PO3 fuera de mezcla con Turtle / Silver. | **NO RESUELTO** — requiere ronda R4 | `t_24fddd4f` §1.2; `engine/po3.py` (`_has_session_range` siempre `False`) |
| `SETUP-GRAMMAR-TEMPORAL` | `SETUP_GRAMMAR_SUPERVISION_V1.md`: 36 features estáticos; sin componente temporal demostrado (plan dice que Helix debe probarlo). | **NO RESUELTO** — no en scope de esta tarjeta | `t_24fddd4f` §1.2; plan §21 |
| `PASS-EDGE-NOT-EXECUTED` | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` declarado; **no ejecutado** porque `BLOCKED_BY_PROVENANCE`. | **NO RESUELTO** — bloqueado | `t_24fddd4f` §8; `.hermes-state/publish_candidate.json` (worktree sucio) |
| `PROVENANCE-BLOCKED` | Checkout sucio (`git status`: modificados + 41 sin track); `engine/execution.py` alterado; `.hermes-state/*` alterado; no hay hash verificado del trabajo de esta tarjeta. | **NO RESUELTO** — requiere limpieza de worktree + commit verificado + hash | `git status`; `publish_candidate.json` |
| `DEDUP-NOT-VERIFIED` | Deduplicación por evento económico (mismo sweep / FVG / PO3) no certificada en código ni en resultados previos. | **NO RESUELTO** — bloquea conteo confiable | Plan §4; `t_24fddd4f` §5.1 |
| `FREQ-NOT-QUANTIFIED` | No hay conteo de candidatos por familia en `VALIDATION`; los conteos previos (292 filas seleccionadas) son exploratorios, no certificaciones. | **NO RESUELTO** — requiere ejecución `FREQ_GATE_2_3_WEEKLY` | `t_24fddd4f` §8 (limitación 2) |

**Regla aplicada:** ninguna de estas deudas se convierte en PASS; se documentan como evidencia de lo que aún falta.

---

## 7. PROVENANCE Y ESTADO DEL WORKTREE (transparencia obligatoria)

- **Rama:** `codex/audit-hermes-cert-20260826`
- **Estado del checkout:** `DIRTY` (5 modificados, 41 untracked, `engine/execution.py` modificado, `.hermes-state/` modificado). No es `CLEAN`; por tanto `PASS_EDGE` **no se declara**.
- **Hash de trabajo de esta tarjeta:** **no generado** (el archivo `cost_economics_preregistration.md` es nuevo y no está indexado en commit verificado; esto es intencional por política de no hacer `git add` general ni push sin auditoría independiente).
- **Fuente de datos:** `data/` existente (inmutable); sin descarga adicional (autorización 2026-09-11 no habilita descarga, solo transformación en memoria y artefactos nuevos permitidos).
- **Licencia:** no solicitada (retirada como bloqueo interno por enmienda 2026-09-11); no modifica dato existente.
- **Artefactos permitidos nuevos:** este archivo (`reports/ict_temporal_v1/orion/cost_economics_preregistration.md`); no modifica `grammar_labels`, splits ni manifiestos existentes.

---

## 8. VEREDICTO CIENTÍFICO DE ESTA TARJETA

**Estado:** `PARTIALLY_SUPPORTED` (mismo que `t_24fddd4f`; esta tarjeta no cambia el veredicto, solo documenta lo congelado y lo pendiente).

**Razón:**
- ✅ Costes económicos congelados con valores declarados y limitaciones documentadas (no inventados).
- ✅ Metodología de frecuencia (`FREQ_GATE_2_3_WEEKLY`) preregistrada con reglas claras, sin optimización post-hoc.
- ✅ Deudas (KZ-2, SB-FVG, PO3-3, DEDUP, PROVENANCE, FRECUENCIA) documentadas explícitamente; ninguna ocultada.
- ❌ No se declara ninguna frecuencia como certificada (falta ejecución determinista con deduplicación y población completa).
- ❌ No se declara `PASS_EDGE` (provenance bloqueado; costes son proxy; datos demo ≠ reales).
- ❌ No se resuelve KZ-2 (honestidad: se deja como deuda, no se inventa reconciliación).
- ❌ No se implementa PO3-3 ni se verifica SB-FVG (fuera de scope de este documento; requiere trabajo de código, no solo documentación).

**Confianza:** `BAJA` (evidencia suficiente para congelar parámetros; insuficiente para cualquier afirmación de edge o frecuencia certificada).

---

## 9. SIGUIENTE EXPERIMENTO / ACCIÓN ESPECÍFICA

Según `t_56fbc441` y `t_24fddd4f` (deuda registradas):

1. **`KZ-2`** → reconciliar `01_KILLZONES.md` con `engine/killzone.py`; proponer un horario único (preferible UTC canónico con conversión ET por `ZoneInfo`, DST comprobado en invierno y verano); documentar la elección y la evidencia que la respalda. No inventar resolución; si la reconciliación no es posible, documentar la contradicción como permanente (`KZ-2-UNRECONCILED`).
2. **`PO3-3`** (métricas aisladas) → implementar o verificar que `engine/po3.py` genera filas `PO3-only` en `METRICS_CANON`; sin esto, `FREQ_GATE_2_3_WEEKLY` no separa PO3 de mezcla.
3. **`SB-FVG`** → modificar `silver_bullet.py` para verificar FVG posterior al sweep (como requiere `07_SILVER_BULLET.md`); sin esto, Silver Bullet no puede certificar estructura.
4. **`DEDUP`** → implementar deduplicación por evento económico (mismo sweep + zona de retorno + KZ) antes de contar; documentar el método.
5. **`PROVENANCE`** → limpiar worktree (`git status` debe ser `clean` para esta tarjeta); generar commit con hash verificado del trabajo; no hacer push sin auditoría independiente (política `local-only` y contrato `completion_contract: local-only`).
6. **`FREQ_GATE_2_3_WEEKLY` ejecución** → solo tras 1–5; contar determinista; reportar `INSUFFICIENT_FREQUENCY`, `PASS_EDGE`, o `MORE_DETERMINISTIC_WORK_REQUIRED` sin inventar.

---

## 10. REFERENCIAS Y ARCHIVOS RELACIONADOS (sin inventar citas)

- `reports/ict_temporal_v1/orion/t_24fddd4f_PROTOCOL_EPISODICO_V1.md` (protocolo base)
- `docs/planificacion/PLAN_ICT_MULTIMODELO_INTRADIA_V1.md` (plan de trabajo, secuencia 1–8)
- `docs/experimentos/EDGE_ECONOMIC_PARAMETERS_DECISION_MEMO.md` (parámetros económicos congelados, proxy)
- `docs/ict/01_KILLZONES.md`, `docs/ict/07_SILVER_BULLET.md`, `docs/ict/08_POWER_OF_THREE.md`, `docs/ict/06_TURTLE_SOUP.md`
- `engine/po3.py`, `engine/silver_bullet.py`, `engine/turtle_soup.py`, `engine/killzone.py`
- `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md` (gate económico; no ejecutado; bloqueado)
- `data/` (universo congelado; inmutable; sin modificación ni descarga adicional)
- `.hermes-state/publish_candidate.json`, `git status` (provenance bloqueado; evidencia real)

---

*Fin del documento. No se declara PASS_EDGE, no se declara frecuencia certificada, no se inventa rentabilidad, no se modifica archivo de datos existente, no se descarga nuevo dataset, no se altera `grammar_labels`. Este archivo es un artefacto permitido nuevo (`reports/ict_temporal_v1/orion/`) que documenta lo que sí está congelado y lo que aún falta, conforme al protocolo de honestidad científica de `ICT SYSTEM` y a la enmienda 2026-09-11.*
