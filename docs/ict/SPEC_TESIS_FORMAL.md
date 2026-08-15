SPEC_TESIS_FORMAL — Contrato fuente de la estrategia ICT/Silver Bullet
==============================================================

ID: SPEC_TESIS_FORMAL.md
Versión: 1.0 (FIRMADA por el comité 2026-07-20 — cumple R1 del roadmap maestro)
Fecha: 2026-07-17 (firmada 2026-07-20)
Estándar: ADR-021 (filosofía documental) + DEC-009e (cadena SPEC→ADS→MDS→CÓDIGO)
Estado: CONTRATO FUENTE (FIRMADA 2026-07-20). Precede al código (R1).
Vinculación: matriz de trazabilidad en ROADMAP_TESIS_DRIVEN_2026-07-17.md §9
            (toda regla aquí debe tener su fila en la matriz; R2 exige sincronía).

> ADVERTENCIA DE VERACIDAD: este documento es la SÍNTESIS CONTRATUAL de
> 20_TESIS_ICT.md + libros 01–08, 13, 15, 16, 17, 18, 21 del repo. NO inventa
> conceptos fuera de ese canon. Cada componente cita su referencia exacta. Si una
> implementación diverge de aquí, LA IMPLEMENTACIÓN está mal (R1: SPEC precede código).

---------------------------------------------------------------------
0. CÓMO SE LEE ESTE CONTRATO
---------------------------------------------------------------------

Cada componente obligatorio de la tesis tiene su bloque con 8 campos:

  ENTrada      · datos/estado que consume
  SALida        · decisión/valor que produce
  PREcondiciones· debe cumplirse antes
  POSTcondiciones· debe cumplirse después
  DEPendencias · otros componentes que deben existir primero
  CRITERIOS     · condición objetiva y medible de "esto es un X válido"
  CASOS LÍMITE  · fronteras donde el criterio se degrada o se omite
  AMBIGÜEDADES  · decisión de ingeniería documentada (no de tesis) o gap abierto

Clasificación por componente (ver matriz §9): OBLIGATORIO / OPCIONAL / DEUDA
FUNCIONAL. Ninguna DECISIÓN DE INGENIERÍA se disfraza de regla de tesis: donde
aplica, se marca explícitamente.

---------------------------------------------------------------------
1. NARRATIVA HTF (sesgo D1/H4/H1)
---------------------------------------------------------------------

Referencia: tesis 20 §1, libro 08 §0. Clasificación: OBLIGATORIO.

ENT: velas cerradas D1, H4, H1 (sesgo del día y de la sesión).
SAL: bias ∈ {BULLISH, BEARISH, NEUTRAL} por TF; alineación D1→H4→H1.
PRE: velas de TF mayor completamente cerradas (sin look-ahead).
POST: sesgo disponible como filtro para ITF/exec.
DEP: ninguna (es la raíz).
CRIT: bias = dirección del último swing estructural mayor confirmado en TF.
CASOS LÍMITE: rango (H1 NEUTRAL) → se acepta como contexto, no anula el setup.
AMBIG: umbral de "estructura mayor" es decisión de ingeniería (ventana de swing).

---------------------------------------------------------------------
2. DEALING RANGE / PREMIUM-DISCOUNT (EQ 50%)
---------------------------------------------------------------------

Referencia: libro 21 (premium/discount). Clasificación: OBLIGATORIO.

ENT: rango del día/sesión (PDH/PDL o Asian range); precio actual.
SAL: zona ∈ {PREMIUM (arriba EQ), DISCOUNT (abajo EQ), EQ}; EQ = 50% del rango.
PRE: rango marcado (open del día o PDH/PDL conocidos).
POST: todo POI se evalúa en discount (long) / premium (short).
DEP: Narrativa HTF (el rango se marca en contexto HTF).
CRIT: EQ = punto medio del rango; premium = precio > EQ; discount = precio < EQ.
CASOS LÍMITE: rango muy estrecho → EQ poco informativo; degradar a sesgo solo.
AMBIG: definición exacta del rango (día vs Asian vs sesión) es decisión de ing.

---------------------------------------------------------------------
3. PD ARRAYS — FVG / OB
---------------------------------------------------------------------

Referencia: tesis 20 §2/§5b, libro 21. Clasificación: OBLIGATORIO.

ENT: velas cerradas LTF (ITF); detección de imbalance.
SAL: zona FVG (gap de 3 velas sin close intermedio) u OB (cuerpo de vela de
     impulso no recuperado).
PRE: desplazamiento (displacement) previo confirmado.
POST: zona disponible como candidata POI.
DEP: Displacement (§5), Narrativa HTF (dirección).
CRIT: FVG = máximo(mínimo 3 velas) vs mínimo(máximo 3 velas) sin solapamiento;
     OB = cuerpo de vela de impulso cuyo 50% no se cierra en contra.
CASOS LÍMITE: FVG muy ancha (gap gigante) → descartar como POI (ruido).
AMBIG: tamaño mín/máx de FVG en ATR es decisión de ingeniería.

---------------------------------------------------------------------
4. PD ARRAYS COMPLETOS — Breaker / Rejection / Mitigation / Propulsion
---------------------------------------------------------------------

Referencia: tesis 20 §5b, libro 21 §2 (tiers T1-T3). Clasificación: OBLIGATORIO.

ENT: estructura rota + retorno; velas cerradas ITF.
SAL: tipo ∈ {BPR, OB, FVG, BREAKER, REJECTION_BLOCK, MITIGATION_BLOCK, PROPULSION}.
PRE: BOS/CHOCH previo (la estructura que se rompió y ahora sirve de zona).
POST: cada bloque etiquetado con su tipo y tier.
DEP: Market Structure (§7), PD Arrays base (§3).
CRIT: BREAKER = estructura rota que el precio respeta como soporte/resistencia;
     REJECTION_BLOCK = vela de rechazo cuyo cuerpo es la zona; MITIGATION_BLOCK =
     OB que mitiga un FVG; PROPULSION = bloque de continuación.
CASOS LÍMITE: bloque muy lejos del precio → no es POI útil (solo contexto).
AMBIG: frontera entre "rejection block" y "OB normal" es decisión de ingeniería.

---------------------------------------------------------------------
5. STACKING MULTI-TF (jerarquía de tiers)
---------------------------------------------------------------------

Referencia: tesis 20 §5b, libro 21 §2. Clasificación: OBLIGATORIO.

ENT: POIs detectados en varios TF (H1, H4, M15, M5).
SAL: tier ∈ {T1=BPR, T2=OB/FVG fuerte, T3=rejection/mitigation}; autoridad
     elevada por apilamiento en mismo nivel de precio.
PRE: al menos un PD Array base en ITF.
POST: POI con tier y score de stacking.
DEP: PD Arrays (§3/§4).
CRIT: T1 > T2 > T3; stacking = POI de TF menor dentro de zona de TF mayor.
CASOS LÍMITE: sin apilamiento → tier por el tipo base solamente.
AMBIG: umbral de "mismo nivel" (tolerancia en pips/ATR) es decisión de ing.

---------------------------------------------------------------------
6. LIQUIDEZ (Sweep)
---------------------------------------------------------------------

Referencia: tesis 20 §3, libro 05. Clasificación: OBLIGATORIO.

ENT: swings agrupados (BSL sobre highs, SSL bajo lows) en banda ATR/margin.
SAL: nivel de liquidez; evento sweep (ruptura + cierre de vuelta adentro).
PRE: estructura previa presente.
POST: sweep validado como trampa (no como entrada).
DEP: Market Structure (§7) para conocer el swing.
CRIT: sweep válido = rompe el nivel Y cierra de vuelta adentro en la MISMA vela.
CASOS LÍMITE: cierre parcial adentro pero mecha larga → aceptar si cuerpo adentro.
AMBIG: ancho de banda de cluster de liquidez es decisión de ingeniería.

---------------------------------------------------------------------
7. DISPLACEMENT
---------------------------------------------------------------------

Referencia: tesis 20 §5b, libro 15. Clasificación: OBLIGATORIO (calibrar en Fase F).

ENT: velas cerradas ITF tras el sweep.
SAL: flag displacement =True/False; dirección.
PRE: sweep validado (§6).
POST: la vela de displacement deja el PD Array para la entrada.
DEP: Sweep (§6).
CRIT: cuerpo de vela > 70% del rango (desplazamiento institucional real).
CASOS LÍMITE: cuerpo 50-70% → displacement débil (bonus, no gate).
AMBIG: umbral 70% y medida del cuerpo son decisión de ingeniería (calibrar).

---------------------------------------------------------------------
8. MARKET STRUCTURE — BOS / CHOCH / MSS
---------------------------------------------------------------------

Referencia: tesis 20 §2, libro 02. Clasificación: OBLIGATORIO.

ENT: swings de TF (ITF/exec).
SAL: evento BOS (ruptura a favor), CHOCH (primera ruptura contraria),
     MSS (= CHOCH + displacement + BOS de confirmación).
PRE: al menos 2 swings formados.
POST: estructura confirmada; dirección del setup definida.
DEP: ninguna (es motor de estructura).
CRIT: BOS = close rompe swing.previo en dirección; CHOCH = close rompe swing
     contrario (aviso de giro); MSS = CHOCH + displacement + BOS.
CASOS LÍMITE: CHOCH sin BOS posterior → solo aviso, no setup.
AMBIG: confirm_bars (velas de confirmación) es decisión de ing (hoy = 2).

---------------------------------------------------------------------
9. 3 CAPAS HTF / ITF / EXEC TF
---------------------------------------------------------------------

Referencia: tesis 20 §5, libro 18 §0. Clasificación: OBLIGATORIO.

ENT: frames disponibles (D1/H4/H1/M15/M5/M1) con roles asignados.
SAL: sesgo (HTF), zona POI (ITF), entry/SL/TP (exec TF).
PRE: el motor recibe htf/itf/exec_tf SEPARADOS (hoy exec_tf==ltf, pendiente).
POST: entry y SL SIEMPRE en exec TF; HTF/ITF solo sesgo y zona.
DEP: ninguna (es marco de temporalidad).
CRIT: regla dura libro 18: SL y entry NUNCA en TF mayor que exec.
CASOS LÍMITE: exec TF no disponible (M1 roto) → degradar a M5, no a H4.
AMBIG: asignación exacta de TF por setup es decisión de ing (ver §16/§17/§18).

---------------------------------------------------------------------
10. EXEC FINO M5 + CONFIRMACIÓN M1
---------------------------------------------------------------------

Referencia: tesis 20 §5, libro 18. Clasificación: OBLIGATORIO.

ENT: frames M5 (entry) y M1 (confirmación).
SAL: señal de entry/SL/TP en M5; confirmación de estructura en M1.
PRE: 3 capas asignadas (§9).
POST: el disparo ocurre en exec TF fino, no en LTF grueso.
DEP: 3 capas (§9).
CRIT: entrada en retorno a zona en M5; SL en mecha de sweep M5.
CASOS LÍMITE: M1 no disponible → confirmar en M5 (sin M1).
AMBIG: ventana de confirmación M1 es decisión de ing.

---------------------------------------------------------------------
11. ENTRY — RETORNO A LA ZONA
---------------------------------------------------------------------

Referencia: tesis 20 §6, libro 15 §2. Clasificación: OBLIGATORIO.

ENT: BOS/CHOCH (§8) + PD Array dejado por displacement (§3/§7).
SAL: señal de entry en el retrace del precio a la zona (no en close del BOS).
PRE: displacement confirmado; PD Array identificado.
POST: entry price = primer retorno a la zona del POI.
DEP: BOS/CHOCH (§8), PD Arrays (§3/§4), POI (§16).
CRIT: entry = retrace a la zona FVG/OB, NO en la mecha del BOS.
CASOS LÍMITE: precio no retorna y sigue → no entry (se pierde el setup, bien).
AMBIG: "retorno" = touch de la zona; profundidad máxima de retrace es decisión ing.

---------------------------------------------------------------------
12. STOP LOSS — ESTRUCTURAL
---------------------------------------------------------------------

Referencia: tesis 20 §7, libros 14/15/17. Clasificación: OBLIGATORIO.

ENT: mecha del sweep (§6); ATR para buffer.
SAL: SL = sweep_low - buffer (long) / sweep_high + buffer (short).
PRE: sweep validado.
POST: SL anclado a estructura, NUNCA ATR puro.
DEP: Sweep (§6).
CRIT: SL = mecha del sweep ± 0.3 ATR; fallback a swing; si no hay nada → None
     (NO opera, no degrada a ATR).
CASOS LÍMITE: sweep gigante → filtro STRUCT_SL_MAX_ATR (6.0) salta el trade.
AMBIG: buffer 0.3 ATR y máx 6.0 son decisión de ing (ya calibrados, medidos v29).

---------------------------------------------------------------------
13. TAKE PROFIT — LIQUIDEZ CERCANA
---------------------------------------------------------------------

Referencia: tesis 20 §8, libros 15/16/17. Clasificación: OBLIGATORIO.

ENT: BSL/SSL del exec TF (§6 clusters reducidos a lo más cercano).
SAL: TP = primer swing de liquidez opuesta MÁS CERCANO al entry.
PRE: dirección del setup definida.
POST: TP en liquidez del LTF, no cluster lejano del HTF.
DEP: Liquidez (§6), 3 capas (§9).
CRIT: TP = BSL/SSL más cercano que el precio toca yendo a favor.
CASOS LÍMITE: liquidez cercana muy lejos → el TP no se alcanza; hold_limit fin.
AMBIG: "más cercano" = distancia en precio al entry; umbral de hold es decisión ing.

---------------------------------------------------------------------
14. LIQUIDEZ INTERNAL vs EXTERNAL
---------------------------------------------------------------------

Referencia: libro 05/15/16, tesis 20 §3. Clasificación: OBLIGATORIO.

ENT: swings recientes (internal) y PDH/PDL/EQ highs-lows (external).
SAL: jerarquía de targets; primero internal, luego external.
PRE: TP base definido (§13).
POST: el TP primario usa liquidez internal; el objetivo macro usa external.
DEP: Liquidez (§6), TP (§13).
CRIT: internal = swing de la sesión/estructura reciente; external = máximos/
     mínimos de día/semana (PDH/PDL, EQ high-low).
CASOS LÍMITE: sin external claro → solo internal.
AMBIG: qué external cuenta (día vs semana) es decisión de ing (contexto HTF).

---------------------------------------------------------------------
15. KILLZONE (London / NY AM / NY PM)
---------------------------------------------------------------------

Referencia: tesis 20 §10, libro 01/18. Clasificación: OBLIGATORIO.

ENT: timestamp del bar; zona horaria correcta.
SAL: flag in_killzone ∈ {London Open, NY AM, NY PM}.
PRE: calendario de sesiones con TZ correcto.
POST: el setup solo es válido dentro de killzone asignada al setup.
DEP: ninguna (es filtro de tiempo).
CRIT: in_killzone(ts) según helper unificado de TZ.
CASOS LÍMITE: TZ mal configurado → killzone falsa (bug conocido libro 01).
AMBIG: bordes de ventana (minutos) son decisión de ing.

---------------------------------------------------------------------
16. POI ANCLADO A NARRATIVA HTF
---------------------------------------------------------------------

Referencia: tesis 20 §5b, libro 21. Clasificación: OBLIGATORIO (BONUS, no gate duro).

ENT: PD Array (§3/§4) + sesgo HTF (§1) + dealing range (§2).
SAL: POI = PD Array que cumple (1) zona correcta P-D, (2) alineado a sesgo HTF,
     (3) creado por displacement real; quality_score += 20 por ancla + stacking.
PRE: PD Array existe; sesgo HTF existe.
POST: POI actúa como BONUS de calidad, NO anula la señal.
DEP: PD Arrays (§3/§4), Narrativa HTF (§1), Dealing Range (§2), Displacement (§7).
CRIT: POI = rol adquirido por PD Array bajo las 3 condiciones; SIN ancla = geometría
     suelta (descartar como POI ICT, pero la zona aún puede ser entry por estructura).
CASOS LÍMITE: POI en wrong-side o EQ → SKIP (no bonus).
AMBIG: CRÍTICA empírica (tests/AUDITORIA_POI_REPORT): POI como filtro DURO destruye
     edge (A'' PF 0.900 vs A' PF 1.511). Por eso es BONUS, no gate. Esto es regla de
     tesis validada por evidencia, no ambigüedad.

---------------------------------------------------------------------
17. SILVER BULLET (SB)
---------------------------------------------------------------------

Referencia: libro 07, tesis 20 §4. Clasificación: OBLIGATORIO.

ENT: killzone NY AM 10-11 ET / NY PM 14-15 ET; M15→M5/M1.
SAL: setup SB listo (sweep LTF + FVG post-sweep + sesgo + RR).
PRE: en killzone; sesgo D1/H4 alineado.
POST: entry en retorno a POI en exec fino; RR por setup = 1:2.
DEP: Killzone (§15), Sweep (§6), PD Arrays (§3), POI (§16), Exec M5/M1 (§10).
CRIT: ready = in_killzone AND sweep AND fvg_after_sweep AND aligned_bias AND rr_ok(1:2).
CASOS LÍMITE: fuera de ventana NY → no SB (aunque haya setup estructural).
AMBIG: RR SB = 1:2 (libro 07 #5) difiere del 1:3 global → se resuelve como RR POR
     SETUP (ver §20). Esto es regla de tesis (libro 07), no ambigüedad.

---------------------------------------------------------------------
18. TURTLE SOUP (contratendencia)
---------------------------------------------------------------------

Referencia: libro 06, tesis 20 §4 (1 de 3 setups del ciclo PO3). Clasificación: OBLIGATORIO.

ENT: killzone London/NY; estructura a favor del HTF rota (sweep manipula).
SAL: setup Turtle Soup listo (sweep en contra + CHOCH contrario confirma giro).
PRE: alineación fallida con HTF (es reversión, no continuación).
POST: entry en retorno tras el CHOCH contrario.
DEP: Sweep (§6), BOS/CHOCH (§8), Killzone (§15), POI (§16).
CRIT: direction == opuesta al sesgo HTF; BOS/CHOCH va CONTRA la marea HTF.
CASOS LÍMITE: si está alineado al HTF → es PO3 (§19), no Turtle Soup.
AMBIG: operar Turtle Soup solo en RANGO (ICT: vive en rango, no tendencia) es
     recomendación de tesis 20 §9; el régimen filter es decisión de ing.

---------------------------------------------------------------------
19. PO3 / AMD (continuación a favor)
---------------------------------------------------------------------

Referencia: libro 08, tesis 20 §1. Clasificación: OBLIGATORIO (setup base).

ENT: sesgo HTF (A) + sweep en contra (M) + CHOCH/BOS a favor + FVG/OB (D).
SAL: po3.complete = A and M and D and aligned.
PRE: las 3 fases presentes.
POST: candidato a entrada solo si complete=True.
DEP: Narrativa HTF (§1), Sweep (§6), BOS/CHOCH (§8), PD Arrays (§3).
CRIT: aligned = setup_dir == bias_dir; si no → es Turtle Soup (§18).
CASOS LÍMITE: solo A+M sin D → trampa hecha, esperar expansión (no entry aún).
AMBIG: "complete" es contrato duro (libro 08); score alto sin complete NO es entry.

---------------------------------------------------------------------
20. RR — MÍNIMO POR SETUP
---------------------------------------------------------------------

Referencia: tesis 20 §9 (1:3, libro 18) / libro 07 #5 (SB 1:2).
           Clasificación: OBLIGATORIO (por setup) — DECISIÓN DE INGENIERÍA el mecanismo.

ENT: SL (§12), TP (§13), setup actual.
SAL: rr = (TP-entry)/(entry-SL); filtro rr >= umbral.
PRE: SL y TP definidos.
POST: el setup pasa el filtro de calidad de RR.
DEP: SL (§12), TP (§13).
CRIT: RR mínimo = 1:3 para PO3/Turtle Soup; 1:2 para Silver Bullet (libro 07 #5).
CASOS LÍMITE: TP en liquidez cercana no alcanza 1:3 → el setup no pasa filtro.
AMBIG: RESUELTA — RR se parametriza POR SETUP (SB usa 1:2, resto 1:3). El valor
     por setup es regla de tesis; el parámetro es decisión de ing (R3: etiquetar).

---------------------------------------------------------------------
21. OTE (Optimal Trade Entry, 62-79% retrace)
---------------------------------------------------------------------

Referencia: tesis 20 §6, libro 15. Clasificación: OBLIGATORIO.

ENT: swing de entry (alto/bajo del displacement); dealing range (§2).
SAL: zona OTE = retrace 62-79% del swing, medido sobre el rango P-D.
PRE: PD Array / zona de entry identificada.
POST: la entrada se refina al nivel OTE dentro de la zona.
DEP: Dealing Range (§2), Entry retorno (§11).
CRIT: entry_price ∈ [0.62, 0.79] del retrace del swing medido desde el extremo.
CASOS LÍMITE: retrace no llega a 62% → entry en zona amplia; >79% → fuera de OTE.
AMBIG: medir el retrace desde el swing completo o desde el PD Array es decisión ing.

---------------------------------------------------------------------
22. TRADE MANAGEMENT (BE / parciales / re-entry)
---------------------------------------------------------------------

Referencia: tesis 20 §9, libro 15/17. Clasificación: OBLIGATORIO.

ENT: posición abierta; estructura en favor.
SAL: acciones BE (mover SL a BE), parcial (cerrar porción en TP1), re-entry.
PRE: trade en favor tras el entry.
POST: gestión activa; no solo hold_limit.
DEP: Entry (§11), TP (§13), Liquidez internal/external (§14).
CRIT: BE tras alcanzar 1R; parcial en liquidez internal; re-entry en nuevo POI.
CASOS LÍMITE: sin estructura a favor → no BE (dejar SL original).
AMBIG: niveles de BE/parcial son decisión de ing (no especificados por tesis como
     umbral fijo; la tesis exige gestión activa, no el número).

---------------------------------------------------------------------
23. SETUPS COMO COMPOSICIÓN (no estrategias distintas)
---------------------------------------------------------------------

La tesis 20 §4 es explícita: PO3 / Turtle Soup / Silver Bullet son el MISMO ciclo
PO3 visto desde distinto ángulo temporal y direccional. No son 3 estrategias. Por
tanto la implementación es UN motor de liquidez con 3 modos:

  PO3        → A+M+D completo, a favor del sesgo    (libro 08, §19)
  Turtle Soup→ M + giro contrario (BOS contra HTF)  (libro 06, §18)
  Silver Bullet→ M + FVG en ventana NY, a favor      (libro 07, §17)

Todos comparten: Sweep (§6) → Displacement (§7) → BOS/CHOCH (§8) → POI (§16) →
Entry (§11) → SL (§12) → TP (§13) → RR (§20) → Trade Mgmt (§22).

---------------------------------------------------------------------
24. REGLAS DE INVALIDEZ (deuda funcional: noticias)
---------------------------------------------------------------------

Referencia: tesis 21 §5. Clasificación: DEUDA FUNCIONAL (regla real, no implementable hoy).

ENT: evento de alto impacto del calendario económico.
SAL: setup invalidado (no opera) si el evento cae en la ventana de holding.
PRE: hook de invalidación documentado en Fase C.
POST: el motor NO opera setups expuestos a noticias de alto impacto.
DEP: Killzone (§15), Trade Mgmt (§22).
CRIT: evento de alto impacto en el horizonte del trade → cancelar/evitar entry.
CASOS LÍMITE: sin feed de noticias → el hook existe pero no se dispara (documentado).
AMBIG: qué cuenta como "alto impacto" es decisión de ing (cuando se conecte feed).

---------------------------------------------------------------------
25. AMBIGÜEDADES GLOBALES RESUELTAS (decisión de ingeniería etiquetada R3)
---------------------------------------------------------------------

Estas no son de tesis; se fijan aquí para no reinterpretarlas por fase:

  - RR por setup: SB=1:2 (libro 07 #5), resto=1:3 (tesis 20 §9/libro 18).
  - confirm_bars BOS/CHOCH = 2 (canónico).
  - SL buffer = 0.3 ATR; STRUCT_SL_MAX_ATR = 6.0 (ya medido v29).
  - POI = BONUS quality_score+=20, NO filtro duro (evidencia AUDITORIA_POI_REPORT).
  - Exec TF default = M15 hoy; M5/M1 pendientes (§10).
  - displacement cuerpo > 70% (calibrar en Fase F).

---------------------------------------------------------------------
26. CONTRATO DE SINCRONÍA (R2)
---------------------------------------------------------------------

Toda regla de este SPEC tiene su fila en ROADMAP_TESIS_DRIVEN_2026-07-17.md §9
(matriz de trazabilidad). Si se agrega/elimina/modifica una regla de la tesis,
AMBOS (este SPEC y la matriz) se actualizan en el MISMO cambio. No se acepta uno
sin el otro.

---------------------------------------------------------------------
FIN — SPEC_TESIS_FORMAL v1.0 — CONTRATO FUENTE (FIRMADA por el comité 2026-07-20).

EXCEPCIÓN REGISTRADA (DEC-009g, 2026-07-20): los componentes B1 (metadatos pd_type/pd_tier),
Fase C (C0-C4, POI anclado como percepción), y A1 Nivel 2 (plan_gate Opción B) se
implementaron ANTES de la firma de esta SPEC. Se reconocen como excepción documentada a R1
(ya validados por tests + call site real + fidelidad, sin alterar conteo de señales). El
resto de la tesis (B2, SB, Turtle Soup, OTE, Trade Mgmt, internal/external liq, killzones
L/NY PM, RR por setup) REQUIERE esta SPEC firmada + su MDS correspondiente antes de
implementarse. Backtest de rendimiento sigue bloqueado hasta Fase G (R4).

MDS (diseño de módulo) por componente: ver docs/specs/ (R2 exige sincronía SPEC↔MDS).
