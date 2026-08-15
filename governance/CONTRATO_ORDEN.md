# Contrato de Orden — edición de código y creación de archivos

> Parte de la gobernanza de `agents/governance/`. Toda edición de código o creación de
> archivo en SMC-SYSTEMS DEBE respetar este contrato. Objetivo: proyecto navegable y
> entregable sin deuda de orden.
>
> Adaptado de `backtest quotex / hermes / CONTRATO_ORDEN.md` a SMC-SYSTEMS.
> Complementario con `PROTOCOLO_AGENTE.md` (obligatorio para todo agente).

## 1. Fidelidad al esquema (README.md / AGENTS.md)
- Toda carpeta tiene UNA responsabilidad. No se mezclan datos, código y experimentos.
- Nunca se crea una carpeta vacía. Solo se crea con contenido real.
- SDD del proyecto (tres ubicaciones con jerarquía, ver `docs/specs/SDD_GOVERNANCE.md` §0):
  `docs/tesis/SDD_*.md` = specs de **diseño de estrategia**; `docs/specs/SDD_GOVERNANCE.md`
  = **meta-SDD** (proceso DoR/DoD/estados/semántica); `docs/specs/INDICE_MDS.md` = índice de
  componentes. `openspec/` = línea base forense **congelada** (no SDD vivo).
  `engine/` es motor; `ict_backtest/` es consumidor; `results/` salidas; `data/` datos;
  `scripts/` herramientas.
- Sigue `AGENTS.md` (Ley Fundamental) y `docs/specs/INDICE_MDS.md`.

## 2. Disciplina de renombres
- Al renombrar, se actualizan TODAS las referencias (grep recursivo) en el mismo cambio.
- Verificación final: grep de la cadena vieja = 0 coincidencias.

## 3. Pre-registro y SDD antes de código
- Nueva lógica de estrategia/detección → va al MOTOR (`engine/`), no al backtest.
- Experimento (lab EXP-NNN): primero SDD + plantilla sellada; luego código.
- Sin tuneo a posteriori sobre los datos de validación.

## 4. Código causal y verificado (Ley del motor)
- Sin look-ahead. Vela a vela. `engine/` NUNCA importa `ict_backtest/`.
- Tests corren antes de declarar listo (`pytest`, `py_compile`, import smoke-test).
- Volumen = única excepción a cero-indicadores; SOLO confirmación (`volume_ratio`), NUNCA gate.

## 5. Sincronización de documentación
- Crear/modificar módulo del motor o SDD ⇒ actualizar `docs/specs/INDICE_MDS.md`,
  `docs/specs/SDD_GOVERNANCE.md` (si cambia proceso) y `AGENTS.md` si cambia la arquitectura.
  No quedan documentos huérfanos.
- Bitácora en `docs/bitacora/bitacora_trabajo.md`.
- Los agentes de gobernanza (`agents/governance/*.md`) se enlazan desde `AGENTS.md` o
  `README.md` para no quedar huérfanos.

## 6. Idioma
- Código, identificadores, comentarios, UI: inglés por defecto.
- Documentación del proyecto: español, salvo que se pida otro idioma.

## 7. Limpieza y cierre
- Sin `hermes-verify-*.py` sueltos ni `__pycache__` commiteado (ver `.gitignore`).
- Código muerto / no cableado → `legacy_smc_backup/` (reversible), no borrado a ciegas.

## 8. Memoria (Engram / bitácora)
- Decisión de arquitectura / patrón → `mem_save` o bitácora. La Memoria Institucional es
  AUTORIDAD del registro; cualquier agente puede escribir su hallazgo y ella lo valida.

Este contrato es el estándar mínimo de orden. `PROTOCOLO_AGENTE.md` lo enforce en cada
tarea; `memoria_institucional.md` lo enforce al decir "es todo por hoy".
