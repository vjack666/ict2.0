# PROTOCOLO DEL AGENTE — Procedimiento obligatorio para todo agente

> Parte de la gobernanza de `agents/governance/`. ESTE DOCUMENTO ES OBLIGATORIO para
> todos los agentes (gobernanza y código). Ningún agente actúa sin seguirlo.
>
> Propósito: evitar que un agente toque el sistema antes de entenderlo. "Entendido, voy a
> modificar X" SIN haber descubierto contexto está prohibido.

## 0. Estados operativos (todo agente debe reportar uno)

| Estado | Significado |
|--------|------------|
| `READY` | Asignado y listo para descubrir contexto. |
| `WORKING` | Ejecutando el protocolo (fases 2–7). |
| `WAITING` | Bloqueado por otro agente/humano; espera input. |
| `BLOCKED` | No puede avanzar; necesita decisión externa (ej. falta SDD). |
| `COMPLETED` | Entregó resultado verificado. |
| `ESCALATED` | Subió al Director (Ruben) por riesgo/falta de autoridad. |

Formato de reporte mínimo:
```
AGENTE: <rol>
TAREA: <qué se le pidió>
STATUS: <estado>
REASON: <por qué, si no es COMPLETED>
ACTION: <qué necesita para avanzar>
```

## 1. NO ACTÚES TODAVÍA
Al recibir una tarea, NO edites nada. El primer instinto es descubrir, no ejecutar.

## 2. DESCUBRE EL CONTEXTO
- Lee `AGENTS.md` (Ley Fundamental), el SDD de diseño de tu componente en `docs/tesis/SDD_*.md`
  (si existe) y el meta-SDD de gobierno `docs/specs/SDD_GOVERNANCE.md` (DoR §1, DoD §2, estados
  §3, verificación semántica §4). Si no hay SDD de diseño para tu componente, pídelo al
  Investigador/Arquitecto y no implementes sin DoR cumplido.
- Identifica a qué componente del motor/backtest afecta (`INDICE_MDS.md`).
- Si es nueva lógica de estrategia → DEBE ir a `engine/` (nunca a `ict_backtest/`).

## 3. LEE LOS CONTRATOS RELEVANTES
- `ROLES_GOBERNANZA.md` (tu rol y límites).
- `CONTRATO_ORDEN.md` (disciplina de edición).
- El contrato de tu rol en esta carpeta (`auditor_independiente.md`, etc.).

## 4. INSPECCIONA EL ESTADO REAL
- Usa grep/read_file para ver el código actual, no asumas.
- Verifica dependencias (qué importa, qué lo importa).
- Confirma que no violas la Ley Fundamental (`engine/` ≠ `ict_backtest/`).

## 5. IDENTIFICA LA FUNCIÓN QUE DEBES CUMPLIR
- ¿Eres ROL (responsabilidad) o instancia de agente para ESTA tarea?
- ¿Qué fase del edificio tocas? (ver `ROLES_GOBERNANZA.md` → metáfora de pisos)
- Si no tienes autoridad para algo (ej. promover a operación), ESCALA, no decides.

## 6. EJECUTA
- Solo tras 1–5. Implementa el cambio reversible (branch/commit aislado).
- En backtest/experimentos: respeta pre-registro SDD (sin tuneo post-hoc).
- Volumen = confirmación, NUNCA gate.

## 7. VERIFICA
- Corre tests (`pytest`), `py_compile`, smoke-test de import.
- Confirma 0 violaciones de la Ley y 0 look-ahead.
- Si algo falla → vuelve a 4, no parchees a ciegas.

## 8. REPORTA
- Indica qué agente generó la salida, qué supuso, y el estado (`COMPLETED`/`BLOCKED`/etc.).
- Incluye evidencia (conteo de tests, grep de verificación), no afirmaciones.

## 9. GUARDA MEMORIA SI CORRESPONDE
- Decisión de arquitectura / patrón → `mem_save` o bitácora (`docs/bitacora/`).
- La Memoria Institucional es AUTORIDAD sobre qué entra al registro, pero cualquier
  agente puede escribir su hallazgo; la Memoria lo valida/estructura (ver su contrato).

## Regla de oro
> Quien propone (Investigador) ≠ quien construye (Ingeniero) ≠ quien audita (Auditor)
> ≠ quien archiva (Memoria) ≠ quien aprueba (Director). El protocolo garantiza el orden.
