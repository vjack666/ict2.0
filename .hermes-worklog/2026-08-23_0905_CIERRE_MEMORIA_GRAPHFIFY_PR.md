# Bitácora — Cierre de memoria compartida + mapa graphify + PR a main

**Fecha:** 2026-08-23 09:05 UTC-5
**Autor:** Hermes (jefe de laboratorio)
**Rama:** feature/a5-audit-datos (HEAD 7e69a0c, PR #8 abierto a main)

---

## Resumen del estado del laboratorio ICT SYSTEM

### Experimento cumplido (18 experimentos totales)
- **Serie A (aislamiento):** A1 PASS, A2 BLOCKED→(A2-FIX FAIL), A3 FAIL, A4 PASS, A5 mixto.
- **Serie B (incrementalidad HTF, 5 micro-agentes en SERIE):** B1 PASS (baseline), B2 FAIL, B3/B4 PASS gate, B5 FAIL. P2 refutada como filtro de sesgo.
- **Serie C (falsación):** C1 EDGE VIVO (GBPUSD), C2 EDGE ROTO (XAUUSD), C3 BLOCKED→(C3-FIX FAIL OOS), C4 EDGE VIVO (costes), C5 INESTABLE (walk-forward).
- **Fixes de deuda (loop de recuperación):** A2-FIX FAIL (−0.39R, TP HTF destruye), C3-FIX FAIL (+0.11R OOS, IC cruza 0), P2-ALT FAIL (+0.34R, Δ IC incluye 0).

### Veredicto científico final
- **P1 (edge LTF depth>=4 existe):** ✅ RESPALDADA (A1, A4, C4).
- **P2 (HTF aporta incremental):** ❌ REFUTADA en TODAS sus formas (sesgo B, TP A2-FIX, estructura P2-ALT).
- **P3 (robustez fuera de muestra):** ⚠️ PARCIAL (vive GBPUSD+costes, muere XAUUSD/tiempo/OOS).

**Conclusión:** el edge ICT en EURUSD H1 vive 100% en el anclaje LTF depth>=4. Cualquier intervención HTF degrada o no mejora. NO promovido a señal.

### Artefactos generados
- `reports/audits/EXP_*` (30 JSON A/B/C + 6 de fixes) — todos en disco y GitHub.
- Bitácoras: `2026-08-21_1012_*`, `2026-08-21_1845_LAB_15EXP_INCREMENTALIDAD`, `2026-08-21_2038_LOOP_CIERRE_DEUDAS`.
- `.hermes-index.md` actualizado.
- **Mapa graphify:** `graphify-out/graph.html` (2753 nodos, 6765 edges, 181 comunidades) + sub-red semántica del lab en `graphify-tmp/chunk_00.json`.
- **PR #8:** https://github.com/vjack666/ict2.0/pull/8 (feature/a5-audit-datos → main, 15 commits, 194 archivos).
- **Engram compartida:** guardado en proyecto `ict2.0` (summary del lab).

### Limpieza
- Archivo basura `NUL` (4 bytes, contenía "test") eliminado del repo local. `git status` limpio.
- `graphify-out/` y `graphify-tmp/` en `.gitignore` (regenerables, no se commitean).

---

## Fase siguiente propuesta (Camino A — filtros LTF puros)
El edge LTF está validado pero tiene deudas de robustez: C5 (walk-forward 2/4) y C3-FIX (OOS frágil). Siguiente micro-agente: testear filtros LTF puros (sesión Londres/NY, rango previo, profundidad exacta=4) para estabilizar el edge SIN tocar HTF. Solo después correr D (evolución) → E (red-team) → Promotion Gate.

---

## Decisiones de sesión (para Engram)
1. **Loop de recuperación:** reintentar SOLO fallas de infraestructura (rate-limit/timeout); FAIL legítimo se respeta, no se fuerza verde (anti-p-hacking).
2. **Concurrencia 1 en serie** para agentes (evitó rate-limit 429 que truncó intentos paralelos).
3. **PR grande (>400 líneas):** un solo PR a main (el trabajo es coherente: cierre de lab + artefactos).
4. **graphify-out en .gitignore:** es regenerable, no se versiona.
