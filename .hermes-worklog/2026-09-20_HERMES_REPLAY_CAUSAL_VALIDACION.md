# Bitácora de Hermes — Validación replay causal H4/M15

**Perfil:** Atlas (CEO operativo)  
**Misión:** Validar y publicar evidencia del commit ddcb09b del replay causal H4/M15  

---

## 2026-09-20 — Ejecución

### Estado inicial del worktree
- Rama: `hermes/evidencia-ict-replay-pass-20260920`
- Commit: `ddcb09b90c6a46912961f500668b9bb14733e893`
- Branch tracking: `origin/gpt/ict-causal-replay-20260920`
- git status: limpio (sin commits locales)

### Bloqueo 1: logs/b1/ faltante
- Causa: `scripts/b1_extract_corpus_v2.py` crea FileHandler en `logs/b1/` al importarse
- La carpeta no existe en `ddcb09b` porque es un artefacto de ejecución, no código fuente
- Solución: copiar `logs/b1/` desde ORIGINAL (contiene log de 4.3KB)
- Resuelto: SI

### Bloqueo 2: datos de entrenamiento faltantes
- Faltan `OOS_REDTEAM_VERDICT.json` y `ai_outcome_v2_full.jsonl.manifest`
- Estos son artefactos de entrenamientos anteriores (2026-08-24), no parte de ddcb09b
- Solución: recuperar desde ORIGINAL
- Resuelto: SI

### Bloqueo 3: hash discrepancies
- ChatGPT reportó hashes SHA-1: `021fad...`, `903891...`, `cff4182...`, `b80baa...`
- Los blobs reales de `ddcb09b` son: `23339a...`, `a86611...`, `74fd768...`, `d0c0b2...`
- Diferencia: ChatGPT reportó hashes de su propio entorno temporal (con CRLF), no de los blobs de GitHub
- Worktree vs blob: diferencias solo por CRLF → contenido funcional idéntico
- Verificado: `git diff` vacío, `diff -q` sin diferencias (sin CRLF)
- Acción: documentado en informe. NO es un problema de integridad del código.

### Suite completa (primera ejecución)
- Resultado: ERROR de recolección (logs/b1/ faltante)
- Después de recuperar logs/b1/: 9 failed, 845 passed, 2 skipped
- 2 fallos por datos faltantes (OOS_REDTEAM_VERDICT.json, manifest)
- 7 fallos por bug de timestamps en pruebas unitarias

### Suite completa (segunda ejecución, datos recuperados)
- Resultado: 7 failed, 848 passed, 1 skipped, 24.68s
- Los 7 fallos son test_integridad_causal_h6_h9.py (bug de timestamps)
- Documentado como: bug de pruebas unitarias, no bug de código de producción

### Verificador A/B
- Ejecutado con EURUSD.zip original desde ORIGINAL
- Resultado: ambos controles PASS_H4_M15_PIT_PILOT
- Control A: 28 objetos, 8 con padre (IDENTICO a ChatGPT)
- Control B: 26 objetos, 6 con padre (IDENTICO a ChatGPT)
- FULL/PREFIX: 12/12 PASS (6 cortes por control)
- Future injection: 2 velas en A, 102 en B (sin cambios)
- SAVE/LOAD, reverse order: PASS

### Dictamen de Vigil
- NO disponible como skill delegable
- Se proporciona el informe técnico completo para auditoría manual

### Publicación
- Pendiente: crear commit con evidencia y hacer push a origin/hermes/evidencia-ict-replay-pass-20260920
