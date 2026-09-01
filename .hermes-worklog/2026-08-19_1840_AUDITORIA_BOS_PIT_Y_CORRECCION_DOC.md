# Worklog — Auditoría BOS/PIT + corrección documental

**Fecha:** 2026-08-19 18:40
**Autor:** Hermes (bajo corrección explícita del Director)
**Plan vigente:** `docs/PLAN_HERMES_FVG_OB.md`, `docs/00_HERMES_START_HERE.md`
**Commit base:** `83cbc9f` → trabajo en `5a3df5d` (doc arquitectura previo)

## 1. Objetivo
Resolver la inconsistencia documentada por el Director entre:
- `docs/ANTI_LOOKAHEAD_MTF_SEQUENCE.md` §5 (afirmaba `detectors.bos.detect_bos` con swings `center=True` = deuda PIT abierta)
- `detectors/bos.py` (código real)
- `docs/SDD_CONTEXT_STATE_MTF_NAVIGATION.md` / `.hermes-index.md` (afirmaban BOS ya causal)

Y corregir `README.md` raíz, que el Director ordenó NO tratar como histórico automático
hasta verificar su estatus en `docs/INDICE_AUTORIDAD.md`.

## 2. Hallazgos

### 2.1 BOS/PIT (evidencia de código)
- `detectors/bos.py:25-46` — `_swing_points` publica el pivote en la barra de
  confirmación `conf = j + lookback`, usando solo barras ya cerradas.
- Comentario explícito línea 28: *"No center=True (no future bars beyond confirmation)"*.
- `grep -n "center" detectors/bos.py` → 0 coincidencias. El detector es **causal**.
- Tests anti-look-ahead: `pytest -k "bos or asof or lookahead"` → **5 passed**.
- `.hermes-index.md` línea 115 (BOS-PIT-01) ya decía CORREGIDO citando `detectors/bos.py`
  sin center=True. El ÍNDICE estaba sincronizado con el código; el SDD anti-lookahead
  §5 estaba desactualizado.

**Veredicto:** el código es causal. NO hubo que corregir BOS. La inconsistencia era
documental (SDD anti-lookahead obsoleto). Camino tomado: actualizar SDD (per tu
instrucción "si SÍ [es causal]: actualizar SDD anti-look-ahead").

### 2.2 README vs INDICE_AUTORIDAD
- `grep -in "readme" docs/INDICE_AUTORIDAD.md` → 0 coincidencias.
- El README **NO está listado** como no-normativo en el índice de autoridad.
- Por tanto, NO se puede ignorar como histórico (corrección #1 del Director).
- El README decía "andamiaje, NO sistema funcional / no se copió el motor" y listaba
  `backtest_validation_graph`/`harness_adapter` como "dependencias rotas" — ambas
  afirmaciones FALSAS en el árbol actual (motor presente; nadie importa esos módulos,
  verificado por grep 2026-08-19).

## 3. Cambios aplicados
1. `docs/ANTI_LOOKAHEAD_MTF_SEQUENCE.md` §5 — tabla de caveats: BOS `center=True`
   marcado como **RESUELTO 2026-08-19** con evidencia (`detectors/bos.py:25-46`,
   tests 5/5). Nota de auditoría añadida.
2. `.hermes-index.md` — BOS-PIT-01 → "CORREGIDO + AUDITADO 2026-08-19"; TNA-01..08 →
   "DISEÑADA / HABILITADA" (antes "PENDIENTE EJECUCIÓN" bajo sombra BOS).
3. `README.md` — bloque de estado corregido a "sistema funcional — motor presente y
   cableado"; sección de "dependencias rotas" reemplazada por nota de que ya no son
   deuda viva; "siguientes fases" reemplazada por estado real (TNA → SEQUENCE×CONTEXT
   → Backtest). Se declaró explícitamente que el README es contexto, no autoridad.

## 4. Tests ejecutados
- `pytest tests/ -k "bos or asof or lookahead or pit or sequence or ahf"` → **5 passed**.
- Import smoke (previo): `engine.ahf`, `engine.sequence`, `agents.orchestrator` OK.
- Suite completa 52/52 (verificada en paso previo del mismo día).

## 5. Decisión / estado
- BOS-PIT: **CERRADO** (causal confirmado por código + tests; SDD actualizado).
- TNA: **HABILITADA** para ejecución (era la sombra que la bloqueaba).
- Backtest / Entry / IA multi-TF: **SIGUEN BLOQUEADOS** hasta A0-A9 + Funnel + TNA.

## 6. Archivos modificados
- `docs/ANTI_LOOKAHEAD_MTF_SEQUENCE.md` (§5)
- `.hermes-index.md` (bloqueadores BOS-PIT-01, TNA-01..08)
- `README.md` (estado, consumidores, siguientes pasos)

## 7. Siguiente acción (según orden del Director)
Ejecutar `ejecuta auditoria temporal` sobre EURUSD 20Y con:
- secuencia real + `precompute_sequences=True`
- AHF real
- PIT + rollback depth + revisitas TF + duración por estado + tiempo hasta condición
  + tiempo de reconfirmación + tamaño FVG/OB en pips + MFE/MAE descriptivos
- Dos gates separados: **TNA-TRACE-INTEGRITY** y **TNA-BEHAVIORAL**
- NO declarar PASS solo por trace válido.
