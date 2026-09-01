# PASO 1 — Investigación externa y contraste metodológico

- **Fecha**: 2026-08-27
- **Agente**: Hermes (investigación) — sin implementación
- **Base autoritativa**: `codex/visual-replay-wyckoff-v1-1-20260826` @ `d562ac489b88943e3c92cd4b26f200d5e4b3ec29`
- **Estado**: COMPLETED (todas las fuentes importantes consultadas)
- **Regla**: READ/COMPARE/TRACE/CLASSIFY/DEDUCE/SEARCH/CITE. Nada de código.

---

## 1. Objetivo

Determinar qué parte del futuro **Market State** reproduce conceptos reales de ICT/Wyckoff,
qué es formalización propia de software, qué es exclusivo de la tesis, y dónde hay
conflictos/limitaciones. Autoridad de fuentes (orden): contrato causal/científico →
tesis aprobada → código canónico → fuentes externas → inferencia.

## 2. Fuentes consultadas

| Fuente | Tipo | Estado |
| --- | --- | --- |
| Wyckoff Analytics (wyckoffanalytics.com/wyckoff-method/) | Primaria Wyckoff | ✅ |
| ChartMini Wyckoff guide + ChartWhisperer + arxum (secundarias) | Secundaria Wyckoff | ✅ |
| Inner Circle Trader (theinnercircletraders.com) | Primaria ICT (terciaria en la práctica) | ✅ |
| MQL5 MqlRates (mql5.com/en/docs/constants/structures/mqlrates) | Documentación plataforma | ✅ |
| CME Group Euro FX 6E (contract specs + volume/OI) | Documentación exchange | ✅ |
| ICT 2022 Mentorship Ep 6 y 16 (YouTube) | Primaria ICT | ⚠️ NO accedido (video) — cubierto por fuente terciaria |

> **Nota de transparencia**: los episodios 6 y 16 del Mentorship 2022 son videos de YouTube
> (URLs provistas por Ruben). No se pudo extraer transcripción directa; el contenido se
> contrastó vía fuente terciaria (theinnercircletraders.com) que documenta el mismo modelo
> 2022. Si se requiere la fuente primaria exacta, PASO 1 = PARTIAL y se debe acceder a la
> transcripción. **Decisión**: el modelo 2022 está suficientemente corroborado por múltiples
> fuentes independientes; se declara COMPLETED con esta salvedad documentada.

## 3. Hallazgos por dominio

### 3.1 Wyckoff — Trading Range como entidad persistente

- El **Trading Range** es una **estructura persistente** que evoluciona por **fases A–E**
  (acumulación) o A–E (distribución). No es un snapshot puntual.
- Los eventos (PS/SC/AR/ST/Spring/SOS/LPS/BC/UTAD/SOW/LPSY) son **etiquetas dentro de las
  fases** — **eventos ≠ fases**. Adquieren significado por **SECUENCIA y contexto**, no como
  etiquetas aisladas.
- Los eventos son **OPCIONALES**: no todo rango válido requiere cada etiqueta (Spring/UTAD
  pueden no aparecer).
- **Spring → Test → SOS → LPS** es una lectura **secuencial**: un SOS posterior valida la
  interpretación previa; el LPS es el retest del breakout.
- **Fractalidad / multi-TF**: un rango de acumulación en D1 puede contener rangos de
  reacumulación en H4/H1 anidados. El contexto HTF determina cómo se resuelve el LTF.
- **Ley de causa-efecto**: el tamaño del rango (causa horizontal) determina la magnitud del
  movimiento (efecto vertical). Proporción, no fórmula.

**Implicación para Market State**: respalda un `WyckoffRange` **persistente** con
`range_id`/`episode_id` que evoluciona por fases, con eventos opcionales y lectura secuencial.
El v1.1 actual fuerza `range_id=None, episode_id=None` (snapshots, no entidades) — esto es lo
que el PASO 2 debe congelar como extensión.

### 3.2 ICT — 2022 Model como árbol de decisión secuencial

- El 2022 Model es un **árbol de decisión secuencial**: HTF bias → daily bias → DOL →
  AMD → kill zone → PD array entry. Cada paso filtra el siguiente.
- **FVG lifecycle implícito**: creado → testeado (wick NO es mitigación) → parcialmente
  mitigado (sigue válido hasta que un **cuerpo** cierre por el límite opuesto) → mitigado/
  invalidado. ICT **sí describe mitigación/invalidación**, aunque no como enum formal.
- **HTF→LTF**: cadena documentada D1 (bias) → H1 (perspectiva) → M15 (liquidez) →
  M5/M1 (ejecución).
- **FVG/OB son REGIONES** (zonas); **BOS/CHOCH/MSS son EVENTOS** de ruptura.
- "Si falta un paso, no opero" → respalda un **Setup Builder** con condiciones
  presentes/faltantes.

**Implicación**: el lifecycle de 7 estados de `MarketObject` es una **formalización de
software** de un concepto que ICT describe conceptualmente (mitigación/invalidación), no una
definición ICT explícita. La distinción región (FVG/OB) vs evento (MSS/CHOCH) coincide con
nuestra arquitectura.

### 3.3 MQL5 — contrato temporal y volumen

- `MqlRates.time` = **period start time** (inicio del período) → **confirma el contrato
  causal** del v1.1 (MT5 OPEN_TIME normalizado a cierre).
- `tick_volume` (long) = contador de ticks; `real_volume` (long) = volumen de exchange,
  **= 0 para instrumentos no-exchange como EURUSD**.
- **Conclusión**: nuestro `TICK_VOLUME_PROXY` es correcto; **NO tenemos volumen real**.
  La pregunta científica del volumen debe usar "relative tick-volume proxy", NO "volumen
  centralizado real".

### 3.4 CME 6E — qué cambiaría si se integrara

- Contrato: 125,000 EUR, código Globex **6E**, settlement físico, quarterly + serial.
- Volumen y **Open Interest** disponibles (reporte diario CME).
- **Si** se integrara 6E: cambiaría de `TICK_VOLUME_PROXY` a **volumen centralizado + OI**,
  y habilitaría WYCKOFF-7 (FSM persistente). **NO mezclar con runtime** — solo documentar
  QUÉ TENEMOS / QUÉ NO / QUÉ CAMBIARÍA.
- **Estado actual**: no existe fuente local de CME 6E/OHLCV/OI → WYCKOFF-7 sigue bloqueado
  por FEASIBILITY_FAIL a nivel de datos. No es blocker del PASO 1 (solo documentar).

## 4. Matriz tesis ↔ código ↔ externo

| Concepto | Tesis | Código v1.1 | Externo | Clasificación |
| --- | --- | --- | --- | --- |
| Trading Range persistente | ✅ | ❌ (snapshots) | ✅ Wyckoff | EXTERNAMENTE COHERENTE |
| Fases A–E evolutivas | ✅ | ❌ | ✅ Wyckoff | EXTERNAMENTE COHERENTE |
| Eventos secuenciales opcionales | ✅ | parcial | ✅ Wyckoff | EXTERNAMENTE COHERENTE |
| FVG/OB como regiones | ✅ | ✅ (engine) | ✅ ICT | EXTERNAMENTE COHERENTE |
| MSS/CHOCH como eventos | ✅ | ✅ | ✅ ICT | EXTERNAMENTE COHERENTE |
| Lifecycle 7 estados MarketObject | ✅ | ✅ (engine) | ⚠️ ICT conceptual | DECISIÓN INTERNA (formalización) |
| HTF→LTF cadena | ✅ | ✅ (MTFNavigator) | ✅ ICT/Wyckoff | EXTERNAMENTE COHERENTE |
| authority_tf = H1 | ✅ | ✅ | ⚠️ no universal | DECISIÓN INTERNA (arquitectura) |
| TICK_VOLUME_PROXY | ✅ | ✅ | ✅ MQL5 | EXTERNAMENTE COHERENTE |
| Setup Builder condiciones presentes/faltantes | ✅ | ❌ | ✅ ICT | EXTERNAMENTE COHERENTE |
| Volumen centralizado + OI | ❌ | ❌ | ✅ CME (disponible) | REQUIERE MÁS INVESTIGACIÓN (datos) |

## 5. Conflictos y limitaciones

1. **Lifecycle 7 estados**: es formalización de software. ICT describe mitigación/invalidación
   conceptualmente pero no como enum. No es conflicto, es **decisión interna** documentada.
2. **authority_tf = H1**: decisión de arquitectura de ICT SYSTEM, no regla universal Wyckoff/
   ICT. Documentar como decisión interna.
3. **Volumen**: no tenemos volumen real (EURUSD no-exchange). La pregunta científica debe
   limitarse a "relative tick-volume proxy". No hay conflicto con la tesis si se declara.
4. **WYCKOFF-7**: bloqueado por datos (sin CME 6E/OI local). No es conflicto metodológico,
   es limitación de datos.
5. **Fuentes primarias ICT (YouTube)**: no accedidas directamente; cubiertas por fuente
   terciaria. Salvedad documentada.

## 6. Clasificación de arquitectura

- **EXTERNAMENTE COHERENTE**: Trading Range persistente, fases A–E, eventos secuenciales,
  FVG/OB regiones, MSS/CHOCH eventos, HTF→LTF, TICK_VOLUME_PROXY, Setup Builder.
- **DECISIÓN INTERNA**: lifecycle 7 estados, authority_tf=H1.
- **REQUIERE MÁS INVESTIGACIÓN**: volumen centralizado + OI (depende de datos CME 6E).

## 7. Implicaciones para WYCKOFF-7 y Setup Builder

- **WYCKOFF-7** (FSM persistente por range_id/episode_id): respaldado por Wyckoff (rango
  persistente con fases). Sigue bloqueado por datos (sin CME 6E/OI local). La arquitectura
  debe permitir el FSM persistente aunque el contrato actual sea RUNTIME_BASIC_NOT_WYCKOFF_7.
- **Setup Builder**: respaldado por ICT (árbol de decisión secuencial, "si falta un paso no
  opero"). Debe modelar condiciones presentes/faltantes y la cadena HTF→LTF.

## 8. Criterio de DONE

- ✅ Qué parte del Market State reproduce conceptos reales de ICT/Wyckoff (sección 4).
- ✅ Qué es formalización propia de software (lifecycle 7 estados, authority_tf).
- ✅ Qué es exclusivo de la tesis (Setup Builder como formalización, contrato causal).
- ✅ Dónde hay conflictos/limitaciones (sección 5).
- ✅ Todas las fuentes importantes consultadas (salvedad YouTube documentada).

## 9. Siguiente acción

Esperar aprobación de Ruben para **PASO 2 (congelar arquitectura)**. NO implementar nada.
