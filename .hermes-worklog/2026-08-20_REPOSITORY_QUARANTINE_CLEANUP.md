# Limpieza de cuarentena del repositorio

**Fecha:** 2026-08-20
**Alcance:** retirar de `ICT SYSTEM` copias exactas de módulos ya conservados
en `C:\Users\v_jac\Desktop\SMC-SYSTEMS`.

## Regla aplicada

Solo se elimina un archivo de ICT cuando:

1. existe una copia en `SMC-SYSTEMS`;
2. el SHA256 coincide;
3. no existen consumidores activos en código, tests o workflows;
4. la política vigente ya no lo autoriza.

## Archivos retirados de ICT

| Archivo | Estado | Evidencia |
|---|---|---|
| `engine/ote.py` | Retirado | SHA256 ICT = SMC; 0 imports activos |
| `detectors/fib.py` | Retirado | SHA256 ICT = SMC; 0 imports activos |
| `engine/rr_by_setup.py` | Retirado | SHA256 ICT = SMC; 0 imports activos |

Las copias quedan disponibles en `SMC-SYSTEMS` como depósito de cuarentena.
No se borró ningún archivo del depósito externo.

## Archivo conservado

`engine/htf_narrative.py` no fue retirado porque su contenido difiere del
depósito externo y existen consumidores activos, entre ellos
`scripts/smoke_motor_lectura.py`. Requiere migración específica antes de una
eliminación segura.

## Validación

- búsqueda de imports: sin consumidores de los tres archivos retirados;
- suite local después de la eliminación: `68 passed`;
- `.hermes/audit_state.json` era un cambio preexistente y queda fuera del commit.
