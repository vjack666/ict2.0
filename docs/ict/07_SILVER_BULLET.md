# ICT — Silver Bullet (intradía / scalping)

| Campo | Valor |
|-------|-------|
| **ID** | `07_SILVER_BULLET.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 |
| **Estado** | Stable (docs) · Needs-code (KZ unificada + model) |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) |

---

## 0. Contrato operativo

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | Dentro de killzone (London Open / NY AM/PM) según helper unificado | Sí |
| 2 | Sweep de liquidez en LTF (típicamente M15) | Sí |
| 3 | FVG posterior al sweep (desplazamiento) | Sí |
| 4 | Alineación con sesgo del día (D1/H4) | Sí (filtro de ruido) |
| 5 | RR ≥ 1:2 (Stellar Lite) | Sí |

**Silver Bullet listo** = #1–#5.

---

## 1. Teoría

Modelo **por tiempo**: sweep + FVG **dentro** de killzone. Ideal scalping M1–M15 con contexto HTF.

---

## 2. Práctica del trader

1. Sesgo del día.  
2. En KZ: esperar sweep.  
3. FVG rápido.  
4. Entrada en retroceso al FVG.  
5. SL estructural; TP liquidez o 1:2.

---

## 3. Algoritmo

```
ready = in_killzone(ts) and sweep and fvg_after_sweep and aligned_bias and rr_ok
```

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Rol |
|-------|------|-----|
| KZ | `detectors/killzones.py`, `rules.killzone_en` | Ventana (TZ a unificar) |
| FVG / sweep | `fvg.py`, pipeline/bos | Trigger |
| Sesgo | `rutina_eurusd.py`, motor observador | Filtro lado |
| UI | `modelo_ict` Silver Bullet | Score |

---

## 5. Auditoría

| ID | Estado |
|----|--------|
| KZ-1 triple reloj | 🔴 R2 |
| Métricas solo SB | 🔴 R4 |

---

## 6. Resultados

[METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11).

---

## 7. Checklist de aplicación

- [ ] `model="silver_bullet"`  
- [ ] KZ unificada  
- [ ] Ablación SB only  

---

## En resumen

Silver Bullet = tiempo (KZ) + manipulación (sweep) + desequilibrio (FVG) + sesgo. Listo en concepto; depende de **killzone honesta** y medición aislada.
