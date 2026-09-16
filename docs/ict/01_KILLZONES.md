# ICT — Killzones (sesiones de actividad institucional)

| Campo | Valor |
| ------- | ------- |
| **ID** | `01_KILLZONES.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 / RFC-001 |
| **Estado** | Stable (docs) · UTC canonico + conversion ET/DST en `engine/killzone.py` |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) |

> **Fuente de verdad:** codigo (`engine/killzone.py`, `detectors/killzones.py`) + este contrato.
> Fuentes externas: innercircletrader.net, litefinance.org (respaldo, no verdad).

---

## 0. Contrato operativo (sí / no)

| # | Condición medible | Obligatorio |
| --- | ------------------- | :-----------: |
| 1 | Existe una **ventana horaria** de alta liquidez definida (London Open y/o NY AM/PM) | Sí |
| 2 | El timestamp de la vela (o reloj vivo) cae **dentro** de esa ventana en la zona acordada | Sí (para Silver Bullet / score KZ) |
| 3 | La zona horaria del cálculo está **documentada** (broker / UTC / ET) y es la misma en UI y backtest | Sí |
| 4 | Fuera de killzone se puede analizar, pero el sistema **baja confianza** o marca “fuera de ventana” | Sí |

**Setup “en killzone”** = #1–#3 verdaderos.  
**Incompleto** = vela fuera de banda o TZ ambigua → no vender como Silver Bullet de alta calidad.

---

## 1. Teoría

Una **killzone** es una ventana de tiempo en la que el *smart money* concentra flujo.  
ICT prioriza **London Open** y **New York AM** (y PM) para setups intradía; fuera de ellas hay más falsas rupturas y CHoCH débiles.

El rango de la sesión **Asian** no es “la killzone de entrada”: define **liquidez del día** (high/low) que luego se barre en London/NY.

---

## 2. Práctica del trader

1. Marcar high/low de Asia como BSL/SSL del día.  
2. Esperar manipulación (sweep) + FVG/CHoCH **dentro** de London o NY AM.  
3. Si no hay setup en London → esperar NY AM (regla clásica).  
4. Fuera de ventana: observar, no forzar scalps.

### Horarios de referencia (ET — mentorship / literatura)

| Killzone | Horario ET (invierno) | Rol |
| ---------- | ---------------------- | ----- |
| Asian | 20:00–23:00 | Rango / liquidez |
| London Open | 02:00–05:00 | Primera ventana fuerte |
| New York AM | 08:30–11:00 | Máxima liquidez |
| New York PM | 13:00–16:00 | Segunda ventana / cierre |

DST: ET se desplaza 1 h en verano. **No mezclar ET con hora broker sin convertir.**

---

## 3. Algoritmo

```
ts = timestamp de la vela (UTC o broker, fijo por pipeline)
h  = hora decimal en la zona canónica del proyecto
kz = etiqueta si h ∈ [ini, fin) de alguna banda
```

**Riesgos**

| Riesgo | Mitigación |
| -------- | ------------ |
| TZ broker ≠ ET | Un solo helper de conversión; documentar default |
| Backtest con reloj PC | Usar **solo** `ts` de vela |
| Chart Shift | No afecta cálculo; solo lectura visual en MT5 |
| Pocas barras | Killzone no depende de profundidad de swings, pero el setup sí |

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
| ------- | ------ | ----- |
| Detector | `detectors/killzones.py` | Columna `kz` / bandas para mapa |
| Motor | `engine/killzone.py` → `killzone_en(ts)` | UTC de entrada, bandas ET convertidas por dia con DST |
| UI | `resumen_widget.py` → `killzone_activa_ahora()` | KZ reloj vivo |
| Mapa | `scripts/mapa_precio.py` | Pintar bandas |

**Estado actual (reconciliacion temporal):**

- La entrada del motor se normaliza a UTC.
- Las bandas economicas siguen definidas en ET y se convierten por fecha con
  `ZoneInfo("America/New_York")`; DST no crea una segunda ruta de evaluacion.
- `detectors/killzones.py` usa la misma conversion ET a UTC para el mapa.

El riesgo de triple reloj queda cerrado tecnicamente. Permanece una
`REVIEW_SCHEDULE_CONTRACT`: los documentos locales no coinciden aun sobre las
horas exactas de NY AM/PM y London para cada modelo. No se certifica frecuencia
de Silver Bullet hasta reconciliar esa definicion de producto.

---

## 5. Auditoría y huecos

| ID | Hallazgo | Estado |
| ---- | ---------- | -------- |
| KZ-1 | Triple definicion de zona (ET / broker / UTC) | ✅ Motor unificado: UTC de entrada + ET/DST por fecha |
| KZ-2 | Horarios exactos de modelo difieren entre documentos locales | ⚠️ REVIEW_SCHEDULE_CONTRACT |
| #1 Look-ahead | No aplica a KZ puras | ✅ N/A |
| Silver Bullet | Depende de KZ correcta | ⚠️ Acoplado a KZ-1 |

---

## 6. Resultados

Killzone no tiene PF propio. Impacta modelos **Silver Bullet** e **intradia**.  
Métricas de cadena: [METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11).

---

## 7. Checklist de aplicación al sistema

- [x] Helper único de zona horaria `app_observador/core/timezone.py` (UTC canónico + display operador)
- [x] UI y backtest importan el mismo helper (`killzone_activa_ahora` en UTC)
- [x] Tests DST para London, NY AM y NY PM (`tests/test_killzone_canonical_time.py`)
- [x] UI muestra "KZ: London Open (UTC 7.0-10.0; operador 2.0-5.0)" explícito
- [ ] Reconciliar por contrato las horas exactas de Silver Bullet antes de contar frecuencia certificada.

---

## En resumen

Killzones son las ventanas donde ICT da más peso al setup. En SMC-SYSTEMS ya se pintan y se usan en checklist, pero hay que **unificar la zona horaria** para que “en killzone” signifique lo mismo en el libro, el mapa, el backtest y el observador.
