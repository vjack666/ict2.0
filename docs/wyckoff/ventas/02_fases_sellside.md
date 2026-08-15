# 02 — Fases A–E de la distribución (sell-side)

El esquema de distribución se divide en 5 fases. Cada una tiene eventos que confirman
que el patrón avanza. Saber qué mirar en cada etapa separa la entrada temprana de perseguir
el quiebre.

## Phase A — Fin de la tendencia alcista
La tendencia agota vapor. Cuatro eventos marcan la transición al rango de distribución:
- **PSY** (Preliminary Supply): primera ola de venta significativa, velas amplias en
  volumen alto que frenan el momentum. La oferta aparece arriba.
- **BC** (Buying Climax): el pico. Surtido alcista de volumen extremo que atrae la última
  oleada de compradores retail. A menudo la vela de MAYOR volumen de todo el chart.
- **AR** (Automatic Reaction): caída brusca tras el BC. Su mínimo define el límite inferior
  del rango de distribución.
- **ST** (Secondary Test): el precio vuelve cerca del nivel BC, pero con volumen claramente
  menor → confirma el sobreabastecimiento en la cima.

## Phase B — Consolidación (el rango)
La fase más larga y la que más engaña. El precio oscila dentro del rango (BC alto ↔ AR bajo)
mientras el Composite Operator sigue distribuyendo. **Upthrusts** (saltos) por encima del
máximo del rango en volumen decreciente son comunes: atrapan compradores de breakout y dan
a las instituciones oferta fresca para vender. **No persigas esos movimientos.**

## Phase C — La última trampa
Contiene el evento más peligroso de todo el esquema:
- **UTAD** (Upthrust After Distribution): quiebre abrupto por encima del máximo del rango
  que *parece* un breakout confirmado. El volumen puede subir al inicio pero no se sostiene.
  Es un shakeout deliberado: los cazadores de breakout compran agresivamente, dándole al
  Composite Operator una última oleada de demanda para vender a lo grande. Una vez atrapados
  los largos, el markdown real comienza.

> No todo patrón produce un UTAD de libro. A veces la Phase C es solo un test silencioso de
> bajo volumen del alto BC que revierte. No esperes el esquema perfecto.

## Phase D — Confirmación de debilidad
La oferta ya manda. Dos eventos lo confirman:
- **SOW** (Sign of Weakness): bajada amplia en volumen alto que rompe el soporte AR. El
  agotamiento de la demanda ya no es ambiguo.
- **LPSY** (Last Point of Supply): el rally débil de baja volumen tras el SOW. El precio no
  recupera el rango porque la oferta aplasta cada rebote. Es la **última ventana de entrada
  short de bajo riesgo** antes de que el markdown acelere.

## Phase E — Markdown
El precio sale del rango de distribución y no mira atrás. El markdown es una caída tendencial
sostenida cuya profundidad es típicamente proporcional al tiempo en el rango (Ley de
Causa y Efecto). Quien leyó la distribución temprano está posicionado; el resto persigue la salida.

---

## En SMC-SYSTEMS (código)

| Fase | Señal en sistema | ICT equivalente |
|------|------------------|-----------------|
| A–B | Sesgo bajista / rango HTF | PO3 A (causa) |
| C UTAD | Exhaustion sobrecompra + sweep BSL | PO3 M |
| D SOW/LPSY | BOS bajista + OB | PO3 D / short |
| E Markdown | Tendencia BEARISH D1/H4 | Continuación short |

- Agente: `agents/wyckoff_agent.py`  
- Cruce: `06_relacion_ict.md` (mapeo Phase B corregido en v2)  
- UI fases: pendiente R7

---
*Espejo:* la acumulación (compras) es idéntica pero invertida — Spring abajo en vez de
UTAD arriba, y el resultado es Markup (alcista), no Markdown.
