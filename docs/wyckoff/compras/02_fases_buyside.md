# 02 — Fases A–E de la acumulación (buy-side)

El esquema de acumulación se divide en 5 fases. Es el espejo de la distribución. Cada fase
tiene eventos que confirman que el patrón avanza.

## Phase A — Fin de la tendencia bajista
La tendencia agota vapor. Cuatro eventos marcan la transición al rango de acumulación:
- **PS** (Preliminary Support): primer soporte: surge demanda inicial tras la caída
  vertical. Velas amplias en volumen alto. No es el mínimo final, es el inicio de la
  estabilización.
- **SC** (Selling Climax): el punto más dramático. Pánico de retail + compra agresiva de
  instituciones. Forma el mínimo del rango. Máximo punto de miedo = inicio de acumulación.
- **AR** (Automatic Rally): rebote veloz tras el SC (la presión vendedora colapsa). Define
  el límite SUPERIOR del rango de acumulación.
- **ST** (Secondary Test): el precio revisa el área SC para testear la oferta. Un ST proper
  muestra volumen menor, low igual o superior, barras más cortas, y falla en quebrar a la
  baja → confirma que la oferta se está absorbiendo.

## Phase B — Construyendo la Causa (el rango)
La fase más larga. Instituciones acumulan posiciones grandes. El precio oscila dentro del
rango (SC/ST abajo ↔ AR arriba). El propósito es **testear la oferta repetidamente** hasta
  que el mercado esté listo para el ciclo alcista. Los swing traders se frustran (chop);
  la acción es intencionalmente confusa. Aquí se construye la *Causa* (Ley 2).

## Phase C — El Spring (sacudida)
El momento de la verdad. El **Spring** es un movimiento deliberado **por debajo del soporte**
diseñado para:
- Disparar los stop-loss del retail.
- Crear pánico.
- Ofrecer a las instituciones precios con descuento profundo.
- Eliminar a los vendedores remanentes.

Un Spring proper suele ser seguido por un **Test** — un retest de bajo volumen que confirma
que la oferta se secó. Si NO hay Spring (el precio hace un higher low en ST y rompe arriba
directo), es el **Schematic 2** (válido también; no esperes Spring en cada setup).

## Phase D — Sign of Strength (SOS) y LPS
Una vez que Spring/Test valida el dominio de la demanda:
- **SOS** (Sign of Strength): rally fuerte que atraviesa la resistencia (el techo del rango).
- **LPS** (Last Point of Support): pullback poco profundo donde los compradores defienden
  niveles más altos. Higher highs y higher lows empiezan a formarse.
- Phase D marca la transición de acumulación al markup temprano.

## Phase E — Markup
La fase explosiva:
- Los breakouts aguantan.
- Los pullbacks se vuelven superficiales.
- Se forman nuevos canales de tendencia.
- Las instituciones escalan en posiciones ganadoras.
El público recién identifica la tendencia aquí — usualmente tarde.

---

## En SMC-SYSTEMS (código)

| Fase | Señal en sistema | ICT equivalente |
|------|------------------|-----------------|
| A–B | Sesgo / rango HTF, agente Wyckoff | PO3 A |
| C Spring | Stochastic exhaustion + sweep SSL | PO3 M / Turtle long |
| D SOS/LPS | BOS alcista + OB | PO3 D / entrada |
| E Markup | Tendencia BULLISH D1/H4 | Continuación |

- Agente: `agents/wyckoff_agent.py`  
- Cruce completo: `06_relacion_ict.md`  
- Checklist aplicación: labels de fase en UI (pendiente R7)

---
*Espejo:* la distribución (ventas) es idéntica pero invertida — UTAD arriba en vez de
Spring abajo, y el resultado es Markdown (bajista), no Markup.
