# Reporte HTF — Bias de hoy + % de Calidad (análisis para IA externa)

**Fecha generación:** 2026-08-16 (sábado, mercado cerrado)
**Responsable:** Hermes (ejecutado bajo directiva de Ruben)
**Alcance pedido:** SOLO HTF (D1/H4/H1). Sin M15/LTF.
**Data más reciente disponible:** 2026-08-14 (viernes, cierre semanal EURUSD).
  Hoy es sábado 2026-08-16 → la "lectura de hoy" = último cierre disponible (2026-08-14).

---

## 0. CONTRASTE DE PREMISA — "el plan de 7 fases ya terminó"

**AFIRMACIÓN recibida:** "ya se terminó el plan de 7 fases, el sistema ejecutará
el motor y va a dar lectura actual".

**VERIFICACIÓN CONTRA CÓDIGO/GIT (REGLA DE ORO):**

| Fuente | Dice |
|---|---|
| `.hermes.md` §20–22 | FASE 0 (estructura inicial), FASE 1 (smoke test), **FASE 2 (motor) EN CURSO**. Cierre de FASE 2 = motor produzca DataFrame real que alimente `AgentOrchestrator` sin `ImportError`. |
| `git log --oneline` | Últimos: `9a639fe` (docs), `712048b` (P1–P5 aprendizaje), `4dd90aa` (P1–P4). NO hay commit de "fase 7" ni hito "plan 7 fases cerrado". |
| `docs/motor_profesional_estado.md` §6 | Puntos abiertos explícitos: solo EURUSD, sin walk-forward, motor viejo sigue como fallback. |

**VEREDICTO:** El motor SÍ ejecuta y SÍ da lectura actual (probado abajo). Pero
**NO hay evidencia de un "plan de 7 fases" en el repo** — el modelo documentado
es FASE 0→2 + sistema de aprendizaje P1–P5. La premisa "7 fases terminadas" es
**NO VERIFICADA / falsa según el repositorio**. El motor opera en estado FASE 2
(funcional pero con deuda abierta), no "cerrado en fase 7".

Esto importa para el análisis externo: el sistema entrega lectura, pero no está
"certificado en 7 fases" — está en operación continua con pendientes conocidos.

---

## 1. PRUEBA EJECUTADA — ¿el motor corre y da lectura?

**SÍ. Evidencia reproducible:**

```bash
cd "C:/Users/v_jac/Desktop/ICT SYSTEM"
.venv/Scripts/python.exe -c "
from engine.bias_from_tools import build_daily_bias
h = build_daily_bias(symbol='EURUSD', month='2026-08')
print(h['d1'], h['h4'], h['h1'], h['direction'], h['aligned'])
"
```

Salida real:
```
D1      : RANGING
H4      : RANGING
H1      : BEARISH (premium)
DIR     : NEUTRAL
ALIGNED : False
```

El motor de lectura HTF está ENCENDIDO (`use_tools=True` por defecto, cableado
desde `712048b`/`66cf1d7`) y compone D1→H4→H1 vía `_compose_htf_bias` con D1
como raíz autoritativa. **Responde a la pregunta: sí, el sistema ejecuta el
motor y da lectura actual.**

**NOTA de integridad (no reportar artefacto):** un primer intento alimentó
`build_htf_narrative` con H4 como los 3 TF (modo proxy) y devolvió BULLISH. Eso
es un artefacto del proxy, NO la lectura HTF canónica. La lectura correcta
HTF-only es la de `build_daily_bias` arriba (NEUTRAL). Se descarta BULLISH.

---

## 2. % DE CALIDAD HTF (HOY)

### 2.1 Componentes medidos (reales, por TF, ventana 800 velas)

| TF | n_CHOCH | CHOCH_real | CHOCH score medio | CHOCH score máx | n_BOS | BOS_real | BOS real-rate | CHOCH class |
|---|---|---|---|---|---|---|---|---|
| D1 | 107 | 0 | 26.0 | 45.3 | 229 | 183 | 79.9% | 107 noise |
| H4 | 125 | 50 | 56.9 | 100.0 | 162 | 121 | 74.7% | 75 noise / 50 premium |
| H1 | 113 | 7 | 30.4 | 95.9 | 155 | 112 | 72.3% | 106 noise / 7 premium |

### 2.2 Índice compuesto de calidad HTF (PROPUESTA, explícito y auditable)

```
HTF_QUALITY% = 0.50 * dir_commit
             + 0.30 * (bos_real_rate_promedio * 100)
             + 0.20 * (choch_score_medio_promedio)

donde:
  dir_commit (compromiso direccional HTF):
     0 TF no-neutral  -> 0
     1 TF no-neutral  -> 20
     2 TF no-neutral igual dir -> 60 ; distinto -> 30
     3 TF no-neutral igual dir -> 100 ; mixto -> 50
  bos_real_rate_promedio = (0.799+0.747+0.723)/3 = 0.756
  choch_score_medio_promedio = (26.0+56.9+30.4)/3 = 37.7

  HTF_QUALITY% = 0.50*20 + 0.30*75.6 + 0.20*37.7 = 10.0 + 22.7 + 7.5 = 40.2
```

### 2.3 RESULTADO

> **HTF_QUALITY% HOY = 40.2 / 100 — CALIDAD BAJA/MEDIA-BAJA.**

Desglose del porqué:
- **Compromiso direccional = 20/100 (muy bajo):** solo H1 no es RANGING; D1 y H4
  están RANGING. El sesgo compuesto es NEUTRAL y NO alineado. No hay convicción
  HTF de dirección hoy.
- **BOS real-rate = 75.6% (bueno):** ~3 de cada 4 BOS pasan el gate geométrico
  de `tools/`. La detección estructural base es sólida.
- **CHOCH score medio = 37.7 (bajo) + real-rate casi nulo:** D1 tiene 0 CHOCH
  reales de 107; H1 solo 7 de 113. Coincide con el hallazgo P3 del sistema de
  aprendizaje (CHOCH M5 = ruido en 92.8%). En HTF el CHOCH también es mayormente
  ruido (D1 100% noise, H1 94% noise, H4 60% noise/40% premium).

**Conclusión para IA externa:** Hoy el HTF no ofrece una lectura de calidad
operativa. Hay estructura BOS válida, pero la dirección HTF no está definida
(D1/H4 laterales) y el CHOCH es ruido. Calidad 40.2% = "estructura presente,
dirección no comprometida, no operar por HTF hoy".

---

## 3. LECTURA HTF DE HOY (resumen)

- **Bias compuesto:** NEUTRAL (D1 RANGING, H4 RANGING, H1 BEARISH premium).
- **Alineación:** NO alineada (solo 1 de 3 TF define dirección).
- **Implicación ICT:** en HTF no hay sesgo de tiempo completo. D1/H4 laterales =
  mercado en rango semanal. H1 bearish premium sugiere presión bajista de muy
  corto plazo DENTRO de un rango mayor. Sin confirmación D1/H4, no es sesgo.
- **Acción sugerida por el sistema:** no tomar lectura HTF como direccional hoy.
  Esperar que D1 o H4 rompa su rango y definan.

---

## 4. PARA ANÁLISIS DE IA EXTERNA — preguntas abiertas

1. **¿Es correcto descartar D1/H4 RANGING como "sin sesgo"?** El motor usa
   `_compose_htf_bias` con D1 raíz. Si D1 es RANGING, ¿debería heredar H4 en vez
   de forzar NEUTRAL? (posible mejora de lógica de composición).
2. **CHOCH real-rate ~0 en D1/H1.** ¿El gate `choch_real` (nivel HL/LH + BOS
   opuesto previo) es demasiado estricto en HTF, o efectivamente el CHOCH HTF es
   ruido? Coherente con P3 (M5 92.8% reclaim) pero ¿se sostiene en D1/H4?
3. **Índice de calidad 40.2% es PROPUESTA, no certificada.** ¿Qué peso dar a
   dir_commit vs bos_real_rate vs choch_score para un "quality%" útil? ¿Falta un
   componente de liquidez/POI?
4. **Pendiente real:** P1–P5 (nature head, rúbrica teacher) aún NO cableado al
   motor en vivo. Solo el modelo ROC 0.798 (CHOCH score) está activo. El reporte
   de calidad usa el scorer de CHOCH cableado, NO la rúbrica nueva.
5. **Solo EURUSD.** El bias/calidad no generaliza a otros pares sin re-entrenar.

---

## 5. ARCHIVOS / EVIDENCIA

- Motor: `engine/bias_from_tools.py::build_daily_bias` (HTF), `engine/htf_narrative.py` (lectura).
- Tools: `tools/{swing,bos,choch,displacement,quality_score,choch_quality,bos_validate}.py`.
- Reproducir: `build_daily_bias(symbol='EURUSD', month='2026-08')`.
- Data: `data/raw/EURUSD/{D1,H4,H1}.parquet` (hasta 2026-08-14).

**Estado Git al generar:** rama `main`, al día con `origin/main`. Untracked:
`scripts/verify_engine.py` (script de verificación útil, sin commitear) y `nul`
(artefacto Windows, basura — ignorar).
