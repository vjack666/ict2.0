# Plan: BOS/CHOCH de calidad superior para Hermes y aprendizaje
**Versión:** 1.1 (revisada post-auditoría, APROBADA)
**Objetivo:** Elevar BOS/CHOCH de detección estructural básica a capa operativa de
calidad superior, de forma que Hermes reciba bias estable y el sistema de
aprendizaje tenga ejemplos de alto valor.

TL;DR: la mejora no es detectar más eventos, sino que SOLO entren al motor los
BOS/CHOCH con estructura real + contexto + continuidad + valor operativo.

---

## 0. Estado actual (ya construido y certificado en GitHub)
- tools/swing.py: SWING objeto persistente cartesiano (id/origin_bar/price).
- tools/bos.py: BOS evento hijo de swing (parent_id).
- tools/bos_validate.py: validador geometrico ACTIVE/INVALIDATED.
- tools/bos_filter.py: filtro tesis (confirm_bars=2 + HTF + fusion + dormido).
- tools/choch.py: CHOCH rompe swing contrario al ultimo BOS, fallback swings.
- tools/displacement.py: RESCATADO de SMC (geometria pura, SIN ATR, rango high-low).
- tools/quality_score.py: RESCATADO de SMC (_compute_bos_quality) -> score 0-1 + is_real.
- tools/choch_quality.py: RESCATADO de SMC (EXP-012) -> CHOCH real (momentum+after-BOS+nivel HL/LH).
- tools/swing_state.py: RESCATADO de SMC (ObjectState) -> fresh/tested/mitigated/invalidated.
- engine/bias_from_tools.py: adaptador que usa TODO lo anterior (Task 5b/Task 6). El
  motor de lectura puede consumir bias_from_tools para uso diario definitivo.

Faltante segun plan 1.1:
- Gate duro como VETO unico (hoy el filtro tesis es suave; el plan exige veto absoluto).
- Score hibrido 0-100 con breakdown en extra (hoy quality_score es 0-1 de SMC).
- Estados raw/rejected_gate/scored/premium en el evento.
- Schema de etiquetado humano + persistencia data/learning por mes.
- Loop de aprendizaje (humano -> modelo) F5.

---

## 1. Principios no negociables
- CHOCH = aviso de giro; BOS = continuidad; MSS = BOS->CHOCH->BOS confirmacion.
- Un solo origen de verdad: tools/ define deteccion + calidad; engine/ consume.
- Separar causa (deteccion) de observabilidad (decision).
- Preservar linaje cartesiano: parent_id + nivel + break_bar.

---

## 2. Filtro duro (GATE) — veto absoluto (PENDIENTE unificar)
Condiciones (todas deben cumplirse para alimentar bias/aprendizaje):
1. Swing de calidad: amplitud minima (k * avg_candle_range, geometria pura) O pivote
   que fue origen de BOS previo. Lookback no fijo 5: usar amplitud minima.
2. Nivel correcto: CHOCH rompe swing contrario al ultimo BOS vigente; BOS a favor.
3. Cierre real: confirmacion por cuerpo, confirm_bars=2.
4. Sin reclaim: el nivel no fue recuperado en N velas (geometrico, ya existe).
5. Desplazamiento minimo: cuerpo >= 1.5 * avg_range y mecha < 40% (tools/displacement).
6. Contexto HTF: clasificar a favor/en contra/neutral (engine/bias_from_tools ya lo pasa).
Falla cualquiera -> evento NO alimenta bias ni dataset de calidad.

## 3. Score hibrido 0-100 (PENDIENTE normalizar de 0-1 a 0-100)
Solo si pasa el gate. Pesos (plan 1.1):
- Estructura 30%, Contexto HTF 20%, Geometria+confluencia 20%, Confirmacion 15%, IA 15%.
El score se guarda en extra con breakdown. >85 premium, 70-84 util, <70 ruido.

## 4. Integracion bias Hermes
Deteccion -> Gate -> Score+Estado -> Bias/Narrative (solo >= umbral) -> Salida+aprendizaje.
Estados: raw / rejected_gate / scored / active/tested/mitigated/invalidated / premium/useful/noise.

## 5. Aprendizaje
Schema etiqueta humana (data/learning/<tool>/YYYY-MM/labels.jsonl):
{event_id,label,human_score,reason,timestamp,symbol,tf}.
Persistir: crudos / gate+score / etiquetas. Trazabilidad: parent_id+nivel+score breakdown.

## 6. Orden repo
tools/ (deteccion+calidad) | engine/ (consumo,bias) | data/learning/ | docs/ict/ | governance/

## 7. Fases entrega
F0 origen verdad | F1 gate duro | F2 score+estados | F3 bias solo validados |
F4 schema etiquetado | F5 loop aprendizaje.

## 8. Verificacion medible
1. Grafico legible (pocos CHOCH/BOS premium por semana M5).
2. Gate: >90% de eventos gate no muestran reclaim inmediato.
3. Bias cambia solo con eventos >= umbral.
4. >=1 mes etiquetado con schema completo.
5. Tercero entiende donde esta definicion/filtro/score.
