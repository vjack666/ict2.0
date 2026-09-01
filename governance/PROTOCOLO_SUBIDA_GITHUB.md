# Protocolo de subida a GitHub

**Estado:** NORMATIVO
**Fecha:** 2026-08-27
**Autoridad:** Cliente (Ruben) — instrucción explícita "sube a github"
**Agente ejecutor:** Hermes (CEO operativo) + subcontratista (identificado en el dictamen)

---

## 1. Objetivo

Definir el protocolo exacto que Hermes ejecuta cuando el cliente dice **"sube a github"**.
Este protocolo NO se ejecuta por iniciativa propia; solo tras la instrucción explícita del
cliente. Respeta la regla del proyecto: `git push` queda prohibido durante el cierre normal;
solo puede ejecutarse después de una auditoría independiente y de una instrucción explícita
de publicación.

## 2. Los 5 pasos

Cuando el cliente diga **"sube a github"**, Hermes ejecuta en orden:

### Paso 1 — Actualizar la bitácora

- Actualizar `.hermes-index.md` (índice maestro) con el estado del trabajo reciente.
- Crear/actualizar el worklog correspondiente en `.hermes-worklog/` con el cierre de la misión.
- Verificar que la bitácora refleje exactamente lo ocurrido (estado, evidencia, riesgos,
  siguiente acción).

### Paso 2 — Actualizar el grafo

- Ejecutar `graphify update .` para mantener el knowledge graph al día (AST-only, sin costo de API).
- Verificar que `graphify-out/` refleje los cambios de código/documentación recientes.

### Paso 3 — Actualizar Engram

- Guardar en Engram el resultado, hallazgos, decisión, riesgos y siguiente acción de la misión.
- Registrar cualquier decisión duradera, convención o descubrimiento relevante.
- Cerrar la sesión con `mem_session_summary` si corresponde.

### Paso 4 — Commit y push

- Revisar `git status --short` y `git diff` para inspeccionar los cambios.
- Crear un commit local selectivo (solo los archivos intencionales de la misión; nunca
  secretos, datos no autorizados ni archivos no relacionados).
- Mensaje de commit en conventional commits (ej: `feat:`, `fix:`, `docs:`, `refactor:`).
- Ejecutar `git push` a `origin` (rama actual).

### Paso 5 — Dictamen CEO

- Escribir al cliente el resumen como CEO, en el formato que usa Codex, del último trabajo.
- Formato del dictamen:

```text
AGENTE: <agente ejecutor>
DEPARTAMENTO: <departamento(s)>
TAREA: <descripción de la tarea>
STATUS: <READY | WORKING | WAITING | BLOCKED | COMPLETED | ESCALATED>
<Mi opinión: análisis técnico y honesto del trabajo>
<Decisión: qué se hizo, qué no, y por qué>
<En resumen: conclusión>
```

- El dictamen debe ser honesto y técnico, sin exagerar logros ni ocultar limitaciones.

## 3. Identificación del subcontratista

En el dictamen, Hermes se identifica como **Hermes** (CEO operativo) y, si participó un
subcontratista, se identifica explícitamente (ej: "Hermes ayudado por <subcontratista>").
El subcontratista se identifica por su rol/agente real que ejecutó el trabajo.

## 4. Reglas de seguridad

- **Nunca** hacer `git push` sin la instrucción explícita "sube a github".
- **Nunca** commitear secretos, credenciales, datos no autorizados ni archivos no relacionados.
- **Nunca** forzar push (`--force`) ni modificar historia remota.
- El commit local selectivo solo incluye los archivos intencionales de la misión.
- Si hay cambios no relacionados en el working tree, NO se incluyen en el commit.

## 5. Criterio de DONE

- ✅ Bitácora actualizada (índice + worklog).
- ✅ Grafo actualizado (`graphify update .`).
- ✅ Engram actualizado (decisiones + resumen de sesión).
- ✅ Commit local selectivo + push a `origin`.
- ✅ Dictamen CEO entregado al cliente en el formato de Codex.
