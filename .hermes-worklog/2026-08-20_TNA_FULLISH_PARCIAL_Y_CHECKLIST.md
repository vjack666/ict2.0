# Bitácora — TNA Full-ish (parcial sandbox) + checklist full local

**Fecha:** 2026-08-20  
**Responsable:** Grok  

## 1. Script entregado

- `scripts/tna_fullish_runner.py`
  - Cobertura: **STRATIFIED_WIDE** (stride configurable, default 40 → ~3.1k steps)
  - Chunks con checkpoint en `reports/audits/ahf_temporal_navigation_FULLISH.checkpoint.json`
  - Salidas: `ahf_temporal_navigation_FULLISH.json` + `.md`
  - **No** declara PASS full-span

## 2. Resultados parciales en sandbox (jobs cortados por límites del entorno)

El sandbox (2 cores / ~2 GB) no pudo completar ~3k steps de un tirón (sesión/filesystem se reinician). Sí se observaron chunks válidos:

| Origen | Steps | Invalidaciones | RB max | TRACE |
|--------|------:|---------------:|-------:|-------|
| STRIDE=30 chunk crisis 08–09 | 400 | 136 | **2.0** | PASS |
| STRIDE=30 chunk ~2011–13 | 400 | 58 | **2.0** | PASS |
| STRIDE=40 chunk ~2012–14 | 350 | 45 | **2.0** | PASS |
| STRIDE=40 chunk ~2014–17 | 350 | 119 | **2.0** | PASS |
| STRIDE=50 chunk ~2010–13 | 300 | 2 | **1.0** | PASS |

**Conclusiones firmes (aunque la corrida full-ish no cerró aquí):**
1. `PASS_TRACE_INTEGRITY` se mantiene en muestreo amplio.
2. **Rollback depth ya no es siempre 0** (max observado 1–2) → fix de instrumentación validado también fuera de la ventana 2017.
3. Con stride muy grande algunos tramos muestran pocas invalidaciones (artefacto de muestreo, no necesariamente del AHF).

## 3. Qué falta para cerrar TNA normativa

| Ítem | Estado |
|------|--------|
| Rollback depth instrumentado | ✅ Fix + evidencia parcial |
| Sandbox multi-ventana | ✅ PASS (commit previo) |
| Full-ish STRATIFIED_WIDE completo | ⏳ Script listo; correr en local |
| Full-span 124k | ⏳ `scripts/tna_audit_runner.py` en máquina ≥12–16 GB |

## 4. Checklist — correr FULL en tu PC

Ver sección en el mensaje al usuario / README implícito:

```bash
git pull origin main
cd datasets/eurusd_dukascopy_20y && sha256sum -c SHA256SUMS && cd ../..

# A) Full-ish (~3k steps, rápido)
python scripts/tna_fullish_runner.py

# B) Full-span normativo (AHF + auditoría canónica)
python scripts/tna_audit_runner.py

# C) Alternativa paralela navegación MTF (no AHF completo)
python scripts/tna_20y_parallel.py
```

Requisitos recomendados para (B): ≥12–16 GB RAM, varios cores, `precompute_sequences=True` ya en el runner.

Tras (B), revisar:
- `reports/audits/ahf_temporal_navigation_20Y.json`
- Gates `TNA-TRACE-INTEGRITY` y `TNA-BEHAVIORAL`
- `rollback_depth_bars.max > 0` si hay invalidaciones
- Etiqueta de cobertura = FULL_SPAN solo si aplica

## 5. Gobernanza

- Partial sandbox ≠ PASS full-span.
- STRATIFIED_WIDE ≠ FULL_SPAN.
- No usar PnL ni edge para aprobar TNA.
EOF
