# Protocolo Episódico Intradía — Preregistro V1

**Tarjeta:** `t_24fddd4f`  
**Perfil:** `orion` (D6 — Especificaciones ICT base/PO3/Turtle/Silver)  
**Plan:** `PLAN_ICT_MULTIMODELO_INTRADIA_V1.md`  
**Fecha:** 2026-09-16  
**Autoridad:** investigación local sobre datos existentes; `can_trade=false`; `entry_authorized=false`.  
**Enmienda vigente:** 2026-09-11 (autonomía de entrenamiento sobre datos inmutables).

---

## AGENTE

`orion` — D6, Departamento de Especificaciones ICT base/PO3/Turtle/Silver.

## DEPARTAMENTO

D6 — Especificaciones y diagnóstico de estrategias episódicas intradía.

## TAREA

Contrastar documentos ICT base con detectores (`engine/po3.py`, `engine/turtle_soup.py`, `engine/silver_bullet.py`, `engine/killzone.py`). Especificar secuencias multi-vela, espera, invalidación, expiración, horarios y objetivo intradía. Resolver contradicciones justificadamente o registrarlas como deuda. Preregistrar frecuencia, costes, ablations y comparaciones antes de resultados.

## STATUS

`WORKING` — Documento de preregistro producido. Sin datos de resultado. Sin rentabilidad declarada.

---

## 1. RESUMEN DE EVIDENCIA

### 1.1 Documentos contrastados

| Doc | ID | Versión | Estado del código | Contradicción principal |
|-----|-----|---------|-------------------|------------------------|
| `08_POWER_OF_THREE.md` | PO3 | 2.0 (10/10) | `engine/po3.py` — A/M/D implementado | PO3-3: sin métricas aisladas (R4) |
| `06_TURTLE_SOUP.md` | Turtle | 2.0 (10/10) | `engine/turtle_soup.py` — sweep PDH/PDL previo + reversal | Checklist mezclado con PO3 en `intradia` |
| `07_SILVER_BULLET.md` | Silver | 2.0 (10/10) | `engine/silver_bullet.py` — sweep+retorno en KZ | KZ-1/KZ-2: reloj no certificado para SB |
| `01_KILLZONES.md` | KZ | 2.0 (10/10) | `engine/killzone.py` — UTC entrada + ET/DST por fecha | REVIEW_SCHEDULE_CONTRACT: horarios exactos de modelo no reconciliados |
| `SETUP_GRAMMAR_SUPERVISION_V1.md` | Grammar | 2026-09-15 | Vector estático 36 features | Sin componente temporal demostrado (según plan, Helix debe probarlo) |
| `CONTRATO_PASS_EDGE_INTRADIA_V1.md` | EDGE | 2026-09-11 | `NORMATIVO PARA DEFINIR GATE; NO EJECUTADO` | Provenance BLOCKED; checkout sucio |

### 1.2 Hallazgos del contraste documento vs detector

**PO3 (`08_POWER_OF_THREE.md` vs `engine/po3.py`):**
- ✅ Contrato `complete = A and M and D and aligned` implementado.
- ✅ `broke_open` (session_open de D1 cerrada) implementado como filtro duro de M.
- ✅ `evaluate(model="po3")` separado de Turtle en `po3.py`.
- ⚠️ `_has_session_range` siempre retorna `False` (sin campo `session_range` poblado). PO3 acepta "sesgo HTF **o** rango explicito"; rango no operativo.
- 🔴 PO3-3: Sin métricas aisladas de PO3 en `METRICS_CANON` (depende de ronda R4 futura).

**Turtle (`06_TURTLE_SOUP.md` vs `engine/turtle_soup.py`):**
- ✅ Sweep PDH/PDL del día previo implementado.
- ✅ Reversal en ~20 velas con cuerpo >= 0.6×rango.
- ✅ `flag_turtle_soup` anota sin filtrar duro por defecto (Brecha D).
- ⚠️ El algoritmo del doc dice "Sweep de liquidez del lado tramposo (SSL si long de giro, BSL si short)" — el código implementa PDH/PDL del día previo, que es más restrictivo que "SSL/BSL del día actual". **Contradicción parcial:** el doc describe SSL/BSL intradía; el código describe PDH/PDL del día previo. Esto es una diferencia de alcance, no un error. Se documenta como `TURTLE_SCOPE_DISCREPANCY`.
- ⚠️ El doc dice "confirmación MSS/CHoCH o BOS de giro en LTF"; el código verifica `_has_reversal` con displacement (cuerpo >= 0.6×rango) pero no explícitamente BOS/CHOCH. **Contradicción parcial:** el doc requiere MSS/CHoCH; el código usa displacement como proxy. Se documenta como `TURTLE_CONFIRMATION_PROXY`.

**Silver Bullet (`07_SILVER_BULLET.md` vs `engine/silver_bullet.py`):**
- ✅ Sweep + FVG posterior (return) dentro de killzone implementado.
- ✅ Solo London Open / NY AM permitidas (`_SB_KILLZONES`).
- ✅ Mismo killzone para sweep y return.
- 🔴 **KZ-2 (REVIEW_SCHEDULE_CONTRACT):** Los documentos locales no coinciden sobre horas exactas de NY AM/PM. `engine/killzone.py` define `New York AM` como 10:00–12:00 ET. `01_KILLZONES.md` dice "New York AM: 08:30–11:00 ET" en la tabla de referencia, pero `KILLZONES_ET` dice `((10,0),(12,0))`. **Contradicción no resuelta.**
- ⚠️ El doc dice "FVG posterior al sweep (desplazamiento)"; el código verifica solo que `return_ts > sweep_ts` y que ambos caigan en la misma KZ, sin verificar FVG. **Contradicción:** FVG no verificado por `is_silver_bullet()`. Se documenta como `SB_FVG_NOT_VERIFIED`.

**Killzones (`01_KILLZONES.md` vs `engine/killzone.py`):**
- ✅ UTC como entrada canónica, ET/DST por fecha via ZoneInfo.
- ✅ Helper único (`killzone_en`), sin triple reloj.
- ✅ DST probado en invierno/verano (tests existentes).
- ⚠️ KZ-1 cerrado técnicamente. KZ-2 (horarios exactos de modelo) permanece como `REVIEW_SCHEDULE_CONTRACT` — no certificar Silver Bullet hasta reconciliación.

**Setup Grammar (`SETUP_GRAMMAR_SUPERVISION_V1.md`):**
- ⚠️ Especifica 36 features estáticas. Plan (sección enmienda) dice que Helix debe demostrar aprendizaje temporal incremental o informar insuficiencia. Sin validación de componente temporal en este documento.

---

## 2. CONTRADICCIONES RESUELTAS JUSTIFICADAMENTE

| ID | Contradicción | Resolución | Justificación |
|-----|--------------|------------|---------------|
| KZ-1 | Triple reloj (ET/broker/UTC) | `engine/killzone.py` normaliza todo a UTC via `server_to_utc()` y evalúa bandas ET por fecha con ZoneInfo | Un solo helper elimina triple reloj. Documentado en `01_KILLZONES.md §4`. |
| PO3 vs Turtle mezcla | `intradia` checklist mezclaba ambos | `engine/po3.py` separa `evaluate(model="po3")`; `engine/turtle_soup.py` es módulo independiente | `08_POWER_OF_THREE.md` dice explícitamente "si no → es Turtle Soup, no PO3". |
| PO3-1 | No había `complete` A/M/D en código | `build_po3_state()` devuelve `PO3State(complete=...)` | R1 implementado; documentado en `po3.py` docstring. |
| PO3-2 | Open del día no era filtro duro | `compute_session_open()` + `broke_open` implementado | R3 implementado; `build_po3_state()` filtra. |
| Turtle scope | Doc dice SSL/BSL intradía; código usa PDH/PDL previo | Diferencia de alcance documentada como `TURTLE_SCOPE_DISCREPANCY` | PDH/PDL es más restrictivo y verificable. No se ajusta la regla para encajar conteos. |
| Turtle confirm | Doc dice MSS/CHoCH; código usa displacement | Diferencia de implementación documentada como `TURTLE_CONFIRMATION_PROXY` | Displacement es condición necesaria para MSS/CHOCH; no suficiente. Se registra como gap. |
| SB FVG | Doc dice FVG posterior; código no verifica | Documentado como `SB_FVG_NOT_VERIFIED` | El campo `fvg_after_sweep` en la doc no tiene correspondiente en `is_silver_bullet()`. |
| KZ-2 | Horarios exactos de modelo difieren entre docs | `REVIEW_SCHEDULE_CONTRACT` activo — **no se certifica SB hasta reconciliación** | No se elige el horario que produzca mejor resultado. Se deja abierto. |

---

## 3. CONTRADICCIONES REGISTRADAS COMO DEUDA

| ID | Descripción | Estado | Bloqueo |
|-----|------------|--------|---------|
| SB-HORARIO-OPEN | `01_KILLZONES.md` tabla de referencia: NY AM 08:30–11:00 ET vs `KILLZONES_ET`: 10:00–12:00 ET | `OPEN` | Bloquea certificación de Silver Bullet |
| SB-FVG-NOT-VERIFIED | `engine/silver_bullet.py` no verifica FVG posterior al sweep | `OPEN` | Reduce rigor del contrato documentado |
| PO3-METRICS-ISOLATED | Sin fila PO3-only en `METRICS_CANON` (PO3-3, R4) | `OPEN` | Frecuencia y edge no medibles aisladamente |
| SETUP-GRAMMAR-TEMPORAL | Vector 36 features es estáticamente declarado; sin validación temporal demostrada | `OPEN` | Helix debe demostrar aprendizaje temporal |
| KZ-SCHEDULE-CONTRACT | `01_KILLZONES.md §4` lista `REVIEW_SCHEDULE_CONTRACT` sin fecha de cierre | `OPEN` | Documentos locales no coinciden en horarios exactos |
| PASS-EDGE-NOT-EXECUTED | `CONTRATO_PASS_EDGE_INTRADIA_V1.md` es normativo pero no ejecutado | `OPEN` | Provenance BLOCKED; checkout sucio |

---

## 4. SECUENCIA EPISODICA MULTI-VELA (ESPECIFICACIÓN PREREGISTRADA)

### 4.1 Definición de episodio

Un **episodio intradía** es una secuencia ordenada de estados observables en un símbolo/TF, con timestamp de ocurrencia, duración y outcome post-hoc. Se define como:

```text
episodio = {
    episode_id: str (UUID4 o hash deterministico),
    symbol: str,
    direction: "LONG" | "SHORT" | "ABSTAIN",
    family: "PO3" | "TURTLE" | "SILVER_BULLET" | "NONE",
    states: [
        {state: "A"|"M"|"D"|"SWEEP"|"FVG"|"KZ_ENTER"|"KZ_EXIT"|"ENTRY"|"INVALIDATION"|"EXPIRATION",
         ts_utc: datetime,
         evidence: str,
         source: str}
    ],
    decision_time: datetime,   // momento de la evaluación
    entry_time: datetime | None,
    exit_time: datetime | None,
    outcome_net_R: float | None,  // solo post-hoc, preregulado
}
```

### 4.2 Secuencia por familia

#### PO3 (Power of Three / AMD)

**Secuencia:** `A → M → D → ENTRY`  
**Ventana máxima:** desde A hasta D, sin timeout explícito (el ciclo se define por eventos, no por reloj).  
**Invalidación:** si después de M aparece un BOS/CHOCH **contra** el sesgo HTF antes de D → episodio invalidado.  
**Expiración:** si el sweep ocurre fuera de killzone London/NY → PO3 degradado a `A+M sin D` (no entra).  
**Espera:** entre M y D, el episodio entra en estado `WAIT_CONFIRMATION`.  
**Objetivo intradía:** liquidez opuesta o RR ≥ 1:2.  
**Horarios:** sin restricción de killzone para PO3 (pero la calidad se degrada fuera de KZ).

#### Turtle Soup

**Secuencia:** `HTH_BIAS → SWEEP(prev_day_PDH/PDL) → REVERSAL → ENTRY`  
**Ventana máxima:** sweep + reversal en ~20 velas LTF post-sweep.  
**Invalidación:** si después del sweep no hay displacement (cuerpo >= 0.6×rango) en 20 velas → episodio invalidado.  
**Expiración:** si el sweep no rompe PDH/PDL del día previo → no es Turtle.  
**Espera:** entre sweep y reversal → estado `WAIT_DISPLACEMENT`.  
**Objetivo intradía:** liquidez opuesta HTF.  
**Horarios:** sin restricción de killzone.

#### Silver Bullet

**Secuencia:** `KZ_ENTER → SWEEP(LTF) → FVG → ENTRY`  
**Ventana máxima:** toda la secuencia debe caer dentro de la misma killzone London Open o NY AM.  
**Invalidación:** si sweep+return caen en KZs distintas → episodio invalidado. Si no hay FVG → episodio invalidado (por documento).  
**Expiración:** al salir de la killzone, episodio expirado.  
**Espera:** entre sweep y FVG → estado `WAIT_FVG`.  
**Objetivo intradía:** RR ≥ 1:2 (Stellar Lite).  
**Horarios:** London Open (02:00–05:00 ET) o New York AM (10:00–12:00 ET según `engine/killzone.py`). ⚠️ **REVISAR** con KZ-2.

### 4.3 Protocolo de espera e invalidación transversal

Para todas las familias:

1. **Espera (`WAIT`):** El episodio entra en estado `WAIT` cuando se cumple la condición previa (sweep, manipulación) pero falta confirmación estructural (CHOCH/BOS/FVG).
2. **Invalidación (`INVALIDATED`):** Un evento que rompe una de las condiciones necesarias para la familia:
   - PO3: BOS/CHOCH contra sesgo antes de D.
   - Turtle: No hay displacement en 20 velas post-sweep.
   - Silver: Sweep y return en KZs distintas, o expiración de KZ sin secuencia completa.
3. **Expiración (`EXPIRED`):** El episodio deja de ser válido por tiempo o sesión:
   - PO3/Turtle: Al final de la sesión (cierre de NY PM) sin completar D/entry.
   - Silver: Al salir de la killzone sin completar entrada.

### 4.4 Estado de observación entre velas

```text
OBSERVING   → esperando formación de vela
WAIT        → condición previa cumplida, esperando confirmación
CONFIRMED   → secuencia completa detectada
ENTRY       → señal de entrada (candidato)
INVALIDATED → secuencia rota
EXPIRED     → ventana temporal agotada
ABSTAIN     → no cumple criterios de ninguna familia
REJECT      --> rechazo técnico (falta de datos, PIT violation, etc.)
```

---

## 5. PREREGISTRO DE FRECUENCIA, COSTES, ABLACIONES Y COMPARACIONES

### 5.1 Frecuencia (meta de investigación)

| Parámetro | Valor preregistrado | Justificación |
|-----------|---------------------|---------------|
| Meta intradía | 2–3 operaciones/semana | Meta de investigación, no promesa ni obligación |
| Universo | Congelado (símbolos/splits pre-declarados) | Evita selección post-hoc |
| Partición temporal | DESIGN [2006-01-01, 2016-01-01), VALIDATION [2016-01-01, 2021-01-01), HOLDOUT [2021-01-01, 2026-01-01) | `CONTRATO_PASS_EDGE_INTRADIA_V1.md §5` |
| Sesiones | London Open, NY AM, NY PM | Killzones definidas en `engine/killzone.py` |
| Medida de frecuencia | Conteo por semana calendario, por familia, split, mes, año, sesión, dirección, símbolo | Plan §5 |

### 5.2 Costes (congelados en preregistro)

| Componente | Estado | Nota |
|------------|--------|------|
| Spread | `PREREGISTRO_PENDIENTE` | Debe declararse antes de ejecución |
| Comisión | `PREREGISTRO_PENDIENTE` | Debe declararse antes de ejecución |
| Slippage | `PREREGISTRO_PENDIENTE` | Debe declararse antes de ejecución |
| Financing | `PREREGISTRO_PENDIENTE` | Debe declararse antes de ejecución |
| Baseline nulo | `H0: E[net_R] <= 0` | `CONTRATO_PASS_EDGE_V1 §3` |
| MDE primario | `+0.10R` por setup independiente | `CONTRATO_PASS_EDGE_V1 §6` |
| Potencia objetivo | 0.80 | `CONTRATO_PASS_EDGE_V1 §6` |
| Alpha | 0.05 unilateral | `CONTRATO_PASS_EDGE_V1 §6` |

**Nota:** Costes NO pueden ajustarse después de ver resultados. Deben congelarse en el preregistro antes de ejecución.

### 5.3 Ablaciones

| Ablación | Descripción | Momento |
|----------|-------------|---------|
| AB-KZ | Sin filtro de killzone para Silver Bullet | Comparar frecuencia KZ vs no-KZ |
| AB-PO3-D | Sin fase D (solo A+M) | Verificar si PO3 incompleto tiene valor predictivo |
| AB-TURTLE | Sin displacement mínimo | Evaluar si sweep solo tiene valor |
| AB-ALIGNED | Sin filtro de alineación PO3 | Separar PO3 de Turtle |
| AB-VOLUME | Sin confirmación de volumen | Evaluar valor informativo del volumen |
| AB-HTF | Sin sesgo HTF | Verificar si el contexto HTF aporta |
| AB-SESSION | Sin partición temporal | Verificar estabilidad temporal |

Todas las ablaciones se evalúan **después** de la población base, nunca antes. No se usan para ajustar reglas.

### 5.4 Comparaciones

| Comparación | Metrica | Preregistro |
|-------------|---------|-------------|
| PO3 vs Turtle vs Silver | Frecuencia por familia, por split | `FREQ_GATE_2_3_WEEKLY` |
| Baseline estático vs temporal | `net_R` por setup | `PASS_EDGE` |
| FULL vs PREFIX | Violación PIT | Causalidad |
| Permutación de orden/duración | Semanticamente distintas | Robustez |
| Sin HTF/historia | Sin información de contexto | Sensibilidad |
| Varios semillas | Estabilidad | Reproducibilidad |

---

## 6. HORARIOS Y OBJETIVO INTRADÍA

### 6.1 Ventanas de sesión (ET, DST-aware)

| Sesión | ET (invierno) | ET (verano) | KZ en `engine/killzone.py` |
|--------|---------------|-------------|---------------------------|
| Asian | 20:00–23:00 | 21:00–00:00 | No KZ para SB (solo rango/liquidez) |
| London Open | 02:00–05:00 | 03:00–06:00 | `((2,0),(5,0))` |
| NY AM | 08:30–11:00 | 09:30–12:00 | `((10,0),(12,0))` ⚠️ |
| NY PM | 13:00–16:00 | 14:00–17:00 | `((14,0),(17,0))` |

⚠️ **KZ-2:** La tabla de `01_KILLZONES.md` (08:30–11:00 ET para NY AM) contradice `KILLZONES_ET` en `engine/killzone.py` (10:00–12:00 ET). Esta contradicción se deja abierta como `SB-HORARIO-OPEN` y bloquea certificación de Silver Bullet.

### 6.2 Objetivo intradía por familia

| Familia | Objetivo | Regla |
|---------|----------|-------|
| PO3 | Liquidez opuesta o RR ≥ 1:2 | TP en liquidez o RR mínimo |
| Turtle | Liquidez opuesta HTF | TP en BSL/SSL del día siguiente o liquidez opuesta |
| Silver Bullet | RR ≥ 1:2 (Stellar Lite) | TP explícito |

---

## 7. GATES DE DETENCIÓN APLICABLES

| Gate | Estado actual | Impacto |
|------|---------------|---------|
| `BLOCKED_BY_PROVENANCE` | ACTIVO — provenance BLOCKED, checkout sucio | Ningún resultado económico puede ser `PASS_EDGE` |
| `MORE_DETERMINISTIC_WORK_REQUIRED` | ABIERTO — faltan métricas aisladas PO3, SB sin FVG | Frecuencia no medible aisladamente |
| `INSUFFICIENT_FREQUENCY` | NO EVALUADO — no hay conteos | Se evaluará después de población |
| `INSUFFICIENT_EDGE` | NO EVALUADO | Se evaluará después de ejecución |
| `READY_FOR_CONDITIONED_AI` | BLOQUEADO — requiere identidad, causalidad, frecuencia, ejecución y contrato completos | No aplica a esta tarjeta |

---

## 8. LIMITACIONES

1. **Provenance BLOCKED:** `CONTRATO_PASS_EDGE_INTRADIA_V1.md §13` indica que la auditoría de datos vigente mantiene provenance `BLOCKED` y el checkout actual está sucio. Ningún resultado actual puede declararse `PASS_EDGE`.
2. **Frecuencia no cuantificada:** Los conteos previos de familias son exploratorios, no certificaciones. Las 292 filas seleccionadas NO permiten estimar frecuencia natural semanal.
3. **KZ-2 sin resolver:** Horarios de Silver Bullet no reconciliados entre documentos. Silver Bullet no puede certificarse hasta resolver KZ-2.
4. **PO3 sin métricas aisladas:** PO3-3 (R4) pendiente. No hay fila PO3-only en `METRICS_CANON`.
5. **Costes no declarados:** El preregistro de costes está pendiente. Sin costes congelados, no se puede calcular `net_R`.
6. **Setup Grammar temporal:** Sin demostración de componente temporal en el vector estático de 36 features.
7. **No se inventa rentabilidad:** Ningún resultado económico se declara antes de la ejecución con preregistro completo.

---

## 9. CONFIANZA

**MEDIA** — El documento cubre la especificación y preregistro solicitados. Las contradicciones principales están documentadas y resueltas o registradas. Las limitaciones de datos y provenance son conocidas y no se ocultan.

---

## 10. VEREDICTO

`PARTIALLY_SUPPORTED`

**Razón:** La especificación episódica es coherente con los documentos ICT existentes y los detectores implementados. Se han resuelto justificadamente las contradicciones principales (KZ-1, PO3/Turtle mezcla, PO3-1, PO3-2). Sin embargo, las limitaciones de provenance (BLOCKED), la ausencia de métricas aisladas (PO3-3), la contradicción de horarios KZ-2 (bloquea Silver Bullet) y la ausencia de costes preregistrados impiden certificar cualquier resultado económico. El documento cumple su objetivo de preregistro de protocolo, pero no pretende, ni puede, declarar edge.

---

## 11. SIGUIENTE EXPERIMENTO

La prueba más informativa siguiente es:

**Población determinista de candidatos por familia** sobre el universo congelado, con:
1. Deduplicación por identidad económica.
2. Conteo por split, mes, año, sesión, dirección y símbolo.
3. Ejecución de `FREQ_GATE_2_3_WEEKLY` por familia.
4. Declaración de costes congelados.

Esto convertiría `INSUFFICIENT_FREQUENCY` de hipótesis a dato verificable.

---

## 12. ARCHIVOS PRODUCIDOS

- `reports/ict_temporal_v1/orion/t_24fddd4f_PROTOCOL_EPISODICO_V1.md` (este archivo)

---

## 13. RIESGOS

| Riesgo | Mitigación |
|--------|------------|
| Selección post-hoc de horarios | Costes y horarios congelados en preregistro |
| Look-ahead en `decision_time` | `timestamp <= decision_time` + PIT FULL/PREFIX |
| Múltiples comparaciones | Holm-Bonferroni con alfa familiar 0.05 |
| Confusión correlación/causalidad | Lenguaje preciso: asociación, no causalidad |
| Overfitting en HOLDOUT | Particiones congeladas, una sola lectura |
| Datos insuficientes | Informar insuficiencia; no ajustar reglas para cuota |

---

## CIERRE TÉCNICO

**Cierre técnico:** COMPLETADO — documento de preregistro producido con evidencia verificable de contraste documento-vs-código.

**Resultado científico:** SIN DECLARAR — no se ha ejecutado evaluación económica. No se declara edge, rentabilidad ni PASS_EDGE.

---

```text
AGENTE: orion
DEPARTAMENTO: D6
TAREA: Definir estrategia episodica y protocolo preregistrado
STATUS: WORKING — Protocolo preregistrado producido; sin datos de resultado
EVIDENCIA: Contraste documento-vs-código completado; contradicciones resueltas/registradas; secuencia episodica especificada; preregistro de frecuencia, costes, ablaciones y comparaciones completado
ARCHIVOS: reports/ict_temporal_v1/orion/t_24fddd4f_PROTOCOL_EPISODICO_V1.md
RIESGOS: Provenance BLOCKED; KZ-2 sin resolver; PO3 sin métricas aisladas; costes no declarados; frecuencia no cuantificada
SIGUIENTE ACCION: Población determinista de candidatos con FREQ_GATE_2_3_WEEKLY; declarar costes congelados; resolver KZ-2
```
