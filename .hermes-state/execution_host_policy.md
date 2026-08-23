# EXECUTION HOST POLICY — ICT 2.0

**Vigente desde:** 2026-08-23
**Dictada por:** Ruben
**Autoridad:** decisión explícita del cliente

## Regla

Todos los experimentos, tests, auditorías, backtests, walk-forwards,
descargas de datos y jobs de laboratorio se ejecutan exclusivamente en el PC
local de Ruben. Esto incluye trabajos livianos y pesados.

## Prohibiciones

- No ejecutar esos trabajos en GitHub Actions ni en runners hospedados por GitHub.
- No transferirlos a Grok, AWS u otra nube.
- No activar un workflow remoto como sustituto de una ejecución local.
- No modificar datasets para resolver una limitación de capacidad.

## Uso permitido de GitHub

GitHub queda como repositorio de código/evidencia, historial, revisión y
sincronización explícitamente autorizada. Un `push` no debe iniciar ejecución
remota. Los workflows históricos se conservan en Git como referencia histórica,
pero no están activos.

## Fallo de capacidad local

Si el PC no tiene capacidad, datos o dependencias para completar el trabajo,
el estado correcto es `WAITING` o `BLOCKED`, con la causa documentada. Nunca se
elige automáticamente un host cloud.

## Evidencia mínima

Toda ejecución local autorizada debe registrar host local, commit, entorno,
dataset/hash, comando, progreso/heartbeat, artefactos y resultado. Un PASS
histórico de CI no autoriza una nueva ejecución cloud.
