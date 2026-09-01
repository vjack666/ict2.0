# Bitácora — Plan TNA pendientes + fix rollback depth

**Fecha:** 2026-08-20  
**Responsable:** Grok (agente)  
**Contexto:** Cerrar pendientes de la tabla TNA tras commit Hermes 1762746 / 6a2534b

## Estado de partida (tabla)

| Aspecto | Estado previo | Acción |
|---------|---------------|--------|
| Integridad de trace (muestra) | PASS (1762746) | Mantener |
| Rollback depth | Roto (siempre 0) | **CORREGIDO en código** |
| Precompute secuencias | OFF en muestra original | Runner ya fuerza True |
| Motor O(n) 20Y | Implementado (6a2534b) | Disponible |
| Script paralelo 20Y | Creado | Disponible |
| TNA full-span 20Y | No ejecutada | **Pendiente de ejecución en máquina con ≥16GB + 20 cores** |
| Clasificación correcta | Actualizada (1b75774) | OK |

## Qué se implementó en este commit

### 1. Fix rollback_depth (auditoría)

**Archivo:** `audits/codigo/ahf_temporal_navigation_audit.py`

**Bug raíz:** el cálculo usaba `parent_state` (nombre de estado AHF, ej. `WAIT_LTF`, `SETUP_READY`) como si fuera un timeframe. Como `"WAIT_LTF"` no está en el mapa de niveles TF, `prev_level` caía a 0 → profundidad siempre 0.

**Solución:** mapeo explícito estado → TF:

```python
state_to_tf = {
    "WAIT_D1": "D1", "D1_LOCKED": "D1",
    "WAIT_H4": "H4", "H4_LOCKED": "H4",
    "WAIT_H1": "H1", "WAIT_LTF": "H1", "SETUP_READY": "H1", "OUTCOME": "H1",
}
```

Luego se calcula `prev_level - target_level` con los niveles D1=0 … H1=2.

### 2. Data loading del runner 20Y

**Archivo:** `scripts/tna_audit_runner.py`

- Prioriza CSV de `datasets/eurusd_dukascopy_20y/` (snapshot completo 2006–2025, SHA256 versionado).
- Fallback a parquet en `data/raw/EURUSD/` si existiera.
- Evita el problema de parquet D1/H4 truncados a ~2020.

### 3. Ejecución full-span

No se completó en este entorno (sandbox con timeout / CPU limitada; 793 barras de la ventana 2017 ya superaban 2 min sin precompute activo en el path AHF).

**Comando listo para ejecutar en máquina adecuada (local o Grok cloud con 20 cores):**

```bash
# 1. Verificar dataset
cd datasets/eurusd_dukascopy_20y && sha256sum -c SHA256SUMS

# 2. Correr TNA full-span (precompute_sequences=True ya configurado)
python scripts/tna_audit_runner.py

# Alternativa paralelizada (navegación MTF, no AHF completo):
python scripts/tna_20y_parallel.py
```

Salidas esperadas:
- `reports/audits/ahf_temporal_navigation_20Y.json`
- `reports/audits/ahf_temporal_navigation_20Y_audit.md`

## Criterio de cierre TNA

Según `audits/PLAN_AUDITORIA_TEMPORAL_AHF.md` §6:

- Dataset 20Y + hash verificable
- Trace reproducible full-span
- Cero PIT
- Rollback **con profundidad > 0 cuando corresponde** (ahora medible)
- Precompute sequences = True
- Cobertura explícita FULL_SPAN en el reporte
- Overall = PASS solo si TRACE-INTEGRITY **y** BEHAVIORAL pasan

## Siguiente acción inmediata (humano / Hermes)

1. Pull este commit.
2. Ejecutar `python scripts/tna_audit_runner.py` en entorno con ≥16 GB RAM.
3. Si overall=PASS → actualizar `.hermes-index.md` y marcar TNA full-span CERRADA.
4. Si FALLA behavioral (ej. nunca SETUP_READY o stuck alto) → diagnosticar diseño de navegación, no relajar gates.

## Nota de gobernanza

Esta bitácora no declara PASS full-span. Solo cierra el bug de instrumentación de rollback y prepara el runner para la corrida definitiva.
