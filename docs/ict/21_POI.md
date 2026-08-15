# ICT — Point of Interest (POI): definición, jerarquía y multi-temporalidad

| Campo | Valor |
|-------|-------|
| **ID** | `21_POI.md` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-15 |
| **Estado** | Marco de aplicación al motor (v30+) |
| **Fuente verdad** | innercircletrader.net (PD Array Matrix), ictkillzone.com (POI Complete Guide), tradingstrategyguides.com (PD Arrays vs SMC POIs), fxopen.com, arongroups.co — contrastado con `20_TESIS_ICT.md` y `18_EJECUCION_OPTIMA_TF_SL_ENTRY.md` |
| **Relaciona** | `03_FVG.md`, `04_ORDER_BLOCKS.md`, `16_TEMPORALIDAD_EJECUCION.md`, `18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`, `20_TESIS_ICT.md`, `MARKET_OBJECT_MODEL.md` (ontología) |

---

## §0 Contrato operativo del POI (CITABLE)

> Un **POI** (Point of Interest) es un **PD Array** (Order Block, FVG, Breaker, Mitigation, Rejection, Liquidity Void, BPR) que cumple TRES condiciones a la vez: (1) está en la **zona correcta del dealing range** (discount para long, premium para short), (2) se **alinea con el sesgo HTF confirmado**, y (3) fue creado por **flujo institucional real** (desplazamiento con cuerpo >70%). El POI NO es un tipo de estructura: es un **ROL** que adquiere un PD Array cuando está en el contexto correcto. Fuera de ese contexto, el mismo FVG/OB no es POI.

Regla dura (corolario de la tesis 18): el POI es la **zona de reacción del ITF** (Intermediate Time Frame), no del HTF ni del exec TF. El HTF da el sesgo; el ITF marca el POI; el exec TF dispara la entrada. El POI vive en el ITF, y el POI de mayor autoridad es el que **apila (stacking)** PD Arrays de varios TF en el mismo nivel de precio.

---

## 1. Qué es un POI (y qué NO es)

**POI = cualquier PD Array en la zona correcta + alineado con sesgo + con respaldo institucional.**

En la comunidad ICT, los traders no dicen "tengo un FVG en 1.0840"; dicen "tengo un **POI** en 1.0840". El POI es el término práctico que colapsa todos los PD Arrays en un único concepto operativo: *una zona de precio donde el algoritmo probablemente reaccionará y donde puedo entrar si las condiciones se alinean*.

Un POI válido exige las TRES condiciones simultáneas:

1. **Zona correcta del dealing range.** Un POI bullish (long) debe estar en la mitad **discount** (debajo del 50% EQ). Un POI bearish (short) debe estar en la mitad **premium** (arriba del 50% EQ). Un OB estructuralmente perfecto en premium en un día bullish NO es un POI bullish válido: el contexto de zona lo hace wrong-side.
2. **Alineación con sesgo confirmado.** El sesgo diario/semanal debe favorecer la dirección del POI. Un FVG bearish sobre sesgo bullish es POI de baja probabilidad. No necesita ser "gritando", pero no puede estar opuesto.
3. **Respaldo institucional.** La zona debe haberse formado por flujo institucional real: una vela de desplazamiento con body-to-range > ~70% (FVG), o la última vela opuesta antes de un move grande (OB). Una zona formada por deriva de bajo volumen o en "dead zone" no tiene la densidad institucional para reaccionar.

**Qué NO es un POI:** un número redondo, una línea estática de soporte/resistencia, una media móvil, o cualquier zona que no fue creada por flujo institucional. En ICT, lo único que califica como POI son los PD Arrays.

> Nota de precisión terminológica: SMC usa "POI" como nombre genérico de la zona; ICT usa "PD Array" como el marco que organiza esas zonas por premium/discount. **Resuelven el mismo problema** (¿de todas las zonas del chart, cuál opero?), pero ICT filtra por *dónde* está la herramienta (zona) y *cuándo* (killzone); SMC filtra por *calidad* (BOS trigger, liquidez de respaldo, fresco, cercanía). Los traders avanzados aplican AMBOS filtros: POI de alta calidad + zona correcta + killzone = triple confluencia.

---

## 2. Jerarquía de tiers del POI (ranking por probabilidad)

No todos los POIs son iguales. Cuando varios PD Arrays caen en la zona correcta, se rankean por calidad:

| Tier | Nombre | Estructura | Tamaño sugerido |
|------|--------|-----------|-----------------|
| **T1 (A)** | **BPR** | OB + FVG superpuestos al mismo nivel (Balanced Price Range) | estándar / elevado |
| **T2 (B)** | OB solo con desplazamiento de calidad | última vela opuesta antes de move grande, cuerpo fuerte | estándar |
| **T2 (B)** | FVG solo con desplazamiento fuerte | cuerpo > ~75% del rango, mayor a velas vecinas | estándar |
| **T3 (C)** | Rejection / Mitigation / Propulsion Block | válidos pero zona menor o dependen de continuación | 50–75% |
| **SKIP** | Cualquier POI en zona wrong-side | OB bullish en premium / FVG bearish en discount / POI en EQ | no operar |

- **T1 (BPR)** = máxima probabilidad: el OB da la referencia de orden institucional; el FVG da el incentivo de rebalanceo algorítmico. Ambos apuntan a la misma zona.
- **T3**: el rejection block tiene SL muy ajustado (rango de mecha estrecho) → alto R:R cuando aguanta, útil a pesar de menor probabilidad base.
- **EQ (equilibrio, mitad central 10–15% del dealing range):** zona de ambigüedad. Los POI aquí tienen menor probabilidad en ambas direcciones; solo operar si sesgo diario Y semanal son fuertes a favor.

**Regla de cantidad:** máximo **2–3 POIs activos por instrumento**. Más = parálisis de decisión; menos = huecos si se pierde el principal.

---

## 3. Multi-temporalidad: el POI y el stacking

El POI se marca y vive en el **ITF**, pero gana autoridad cuando **apila (stacking)** PD Arrays de múltiples TF en el mismo nivel de precio. Esto es la versión multi-TF del BPR T1.

**Jerarquía de stacking (de más débil a más fuerte):**

1. **Un TF, una estructura:** solo FVG en M5. Suficiente para entrar, pero menor probabilidad. Requiere sesgo y killzone perfectos para compensar la falta de confirmación HTF.
2. **Un TF, dos estructuras:** BPR en M15 (OB+FVG al mismo nivel). El POI T1 estándar. Fuerte por sí solo con buen sesgo.
3. **Dos TF, misma dirección:** **OB de M15 dentro de FVG de H1.** El H1 da la zona macro de imbalance; el M15 da el nivel de entrada exacto dentro de ella. Entrar en el 50% CE del OB de M15, estando dentro del FVG de H1, es una de las entradas ICT de más alta probabilidad (SL más ajustado, dos TF confirman).
4. **Tres TF apilados:** OB de M5 dentro de FVG de M15 dentro de OB de H1. Densidad institucional máxima en esa zona. Raros (1–2 por semana) pero reacción más limpia y SL más ajustado.

**Flujo de preparación (Sunday prep, estilo ICT real):**
1. Sesgo y draw on liquidity semanal (BSL/SSL).
2. Dealing range diario: swing high/low, calcular EQ (50%). ¿Precio en premium, discount o EQ?
3. Escanear **diario y H4** buscando PD Arrays en la zona correcta (OB/FVG/BPR por debajo del EQ si bullish).
4. Rankear por tier, elegir top 2–3 POIs (los más cercanos al precio y de mayor tier).
5. Alerta de precio en el **50% CE** (midpoint del cuerpo del OB o rango del FVG) de cada POI. Al disparar, bajar al M5 y aplicar el entry.

> Clave: el POI se marca en HTF/ITF (diario/H4/M15) pero la **entrada y el SL se resuelven en el exec TF** (M15/M5/M1), nunca en el TF mayor (tesis 18). El POI es la zona; el exec TF es el disparo.

---

## 4. El POI como nodo de NARRATIVA (brecha que el código debe cerrar)

Un POI suelto (cualquier FVG/OB en ventana) NO es un POI ICT real. El POI real está **anclado a una narrativa**: el desplazamiento estructural que lo creó.

- El POI bullish nace de un desplazamiento alcista institucional (BOS/CHOCH en esa dirección en el TF padre).
- Sin ese ancla, el FVG/OB es solo geometría suelta: existe, pero no tiene "por qué" el precio reaccionaría ahí.
- La auditoría empírica del proyecto (`tests/AUDITORIA_POI_REPORT.md`, 10.669 zonas medidas) demostró que el sistema actual marca "POI" = cualquier FVG/OB en ventana de 20 velas H4, y que el **100%** de esos POI aceptados carecía de un BOS/desplazamiento HTF que los respaldara. Eso es "todo FVG/OB = POI", no un POI de narrativa.

**Contrato de código (cierra ontología → biblioteca → código):**
- Un POI solo cuenta si está anclado a un desplazamiento estructural en su dirección en el TF padre (BOS/CHOCH de HTF en las últimas N velas).
- El POI es un **BONUS de calidad** (`quality_score += 20` según `MARKET_OBJECT_MODEL.md`), NO un filtro duro que anule la señal. La auditoría demostró que usar POI HTF como filtro duro destruye el edge (A'' PF 0.900 vs A' PF 1.511).
- Stacking multi-TF eleva el tier: un OB de M15 dentro de un FVG de H1 es POI T1 apilado, no dos POIs distintos.

---

## 5. Invalidación del POI (cuándo borrarlo)

Saber cuándo eliminar un POI es tan importante como marcarlo:

1. **Cierre de cuerpo por el límite lejano del POI:** si el cuerpo cierra debajo del low del OB (bullish) o por encima del high (bearish), la zona falló → borrar (es la prueba de breaker aplicada al POI).
2. **Cambio de sesgo contra la dirección del POI:** si el sesgo semanal gira a bearish, el POI bullish ya no está en contexto válido → reevaluar, no operar en la dirección original.
3. **Edad > 3–5 sesiones sin test:** los PD Arrays decaen en relevancia institucional. Frescos (<= 3–5 sesiones en el exec TF) siempre preferibles a viejos.
4. **Consumo por noticia de alto impacto:** si el precio atraviesa el POI impulsivamente por un evento, la zona fue consumida, no testeada → marcar estructuras frescas post-noticia.

---

## 6. POI en el motor SMC-SYSTEMS (mapeo a código)

| Concepto ICT (este doc) | Estado en el repo | Acción |
|--------------------------|-------------------|--------|
| POI = PD Array en zona correcta + sesgo + respaldo | `ict_backtest/market_object.py` tiene `role=POI` pero NO filtra zona/sesgo/respaldo | Implementar los 3 filtros en `build_objects` |
| Dealing range / premium-discount (50% EQ) | No existe en el código | Nuevo: calcular EQ del dealing range por TF |
| Tier hierarchy (BPR > OB/FVG > bloques) | No existe | `quality_score` por tier (BPR +bonus) |
| Stacking multi-TF | `_htf_has_poi` mira ventana de 20 velas H4 (demasiado ancho, sin ancla) | Reemplazar por ancla narrativa + stacking |
| POI como BONUS, no filtro duro | Fase E lo usó como filtro duro (A'' 0.9) | Cambiar a `quality_score += 20` (ontología) |
| Invalidación por cierre de cuerpo / edad | `market_structure.py` ya event-driven (sin aged) | Reusar lógica de invalidación para POI |

---

## 7. Checklist de aplicación al sistema (v30+)

- [ ] `build_objects`: cada FVG/OB recibe `role` según zona + sesgo + respaldo (no todos son POI).
- [ ] Nuevo módulo `dealing_range`: EQ = 50% fib del swing high/low del HTF; clasificar zona premium/discount.
- [ ] `quality_score`: +tier (BPR > OB/FVG > bloques) + stacking multi-TF + ancla narrativa HTF.
- [ ] POI = BONUS de `quality_score`, NO gate duro (corregir Fase E).
- [ ] `_htf_has_poi`: reemplazar ventana ciega de 20 velas por "¿hay BOS/CHOCH HTF en dirección del POI en ventana N?" (ancla narrativa).
- [ ] Invalidación de POI por cierre de cuerpo + edad (reusar event-driven existente).
- [ ] Tests: POI anclado da +score; POI sin ancla NO cuenta; stacking eleva tier.

---

## En resumen

El POI ICT no es "cualquier FVG/OB": es un **PD Array en la zona premium/discount correcta, alineado con el sesgo HTF y con respaldo institucional**, rankeado por tier (BPR > OB/FVG > bloques) y elevado por **stacking multi-TF**. El POI vive en el ITF; la entrada y el SL se resuelven en el exec TF. El POI correcto del código debe estar **anclado a una narrativa** (desplazamiento HTF) y actuar como **bonus de calidad**, no como filtro que anula señales. Este doc cierra el ciclo ontología (`MARKET_OBJECT_MODEL.md`) → biblioteca (`21_POI.md`) → código (`ict_backtest/`).
