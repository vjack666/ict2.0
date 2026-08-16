# Bitácora — Task 4 CORRECCIÓN: CHOCH en todas las TFs (bug detectors.choch)

**Fecha:** 2026-08-15 20:40 UTC-5
**Plan:** `.hermes/plans/2026-08-15_143000-individual-tools-m5-learning.md`
**Veredicto del Director:** "debe haber CHOCH en todas las temporalidades; si no,
¿dónde se conoce el giro? Revisa la tesis y corrige."

---

## Diagnóstico (documentado en tesis 02_MSS_CHOCH.md)
BUG 1: detectors.choch usaba `close.rolling(50)` para contexto. En D1 solo
hay 24 velas del mes -> rolling(50)=NaN -> 0 CHOCH. Frágil y NO es la tesis.
BUG 2: CHOCHTool leía signals SW_SL/SW_SH; SwingTool emite SWING_HH/HL/LH/LL.
BUG 3: mi CHOCH requería "ultimo BOS" -> en D1 sin BOS = 0 CHOCH.

## Definición correcta (tesis §0 #2, §1, §3 A6)
CHOCH = primera ruptura del swing CONTRARIO, idealmente del nivel del ultimo BOS.
NO depende de medias móviles. Fallback: si no hay BOS previo, inferir marea
de la pendiente de los ultimos 2 swings del mismo tipo.
A6: histórico corto -> pocos swings -> necesita >=3-4 años de datos.

## Corrección aplicada
tools/choch.py REESCRITO: logica pura de swings/BOS (aislada, sin detectors.choch
ni engine/). Mapeo SWING_HL/SWING_LH correcto. Fallback de marea por swings.
tools/bos_filter.py: guarda acepta ("BOS_","CHOCH_") + summarize cuenta ambos.

## Resultado (EURUSD)
Recorte 1 mes (2026-07-14..08-14) en TFs menores:
```
TF     CHOCH_total  valid  unicos  up  dn
M5       1250        20     20      0   20
M15       428         9      9      0    9
H1         76         2      2      0    2
H4          7         1      1      0    1
D1          0         0      0      0    0   <- 24 velas: insuficiente (A6)
```
D1 con histórico amplio (800 velas, ~3 años) -> 97 CHOCH, 5 unicos (0 up/5 dn).
H4 con 1500 velas -> 43 CHOCH, 1 unico.

CONCLUSION: el codigo ahora SI detecta CHOCH en todas las TFs. El "0 en D1" era
ventana de 1 mes insuficiente (A6), no bug de deteccion. Para TFs grandes se
debe usar histórico amplio; el recorte de 1 mes solo aplica a M5/M15/H1.

## Hallazgo de aprendizaje
Sesgo alcista del mes persiste: todos los CHOCH unicos son DOWN (giro bajista
aviso). El filtro tesis + fusion reduce 1250->20 en M5 (misma leccion que BOS).

## Siguiente
Task 5+: FVG / OB. Luego Fase 2 (aprendizaje humano) + grafico CHOCH.
