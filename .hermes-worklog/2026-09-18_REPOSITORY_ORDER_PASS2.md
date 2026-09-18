# Segunda pasada de ordenamiento del repositorio — 2026-09-18

## Objetivo

Preparar una estructura física limpia sin romper el repositorio activo.

## Resultado

- se auditó la raíz de `entrenamiento-ia`;
- se confirmó que las capas principales ya existen y están razonablemente separadas;
- se identificó la raíz como principal foco de desorden;
- se eliminó el archivo vacío accidental `Executable`;
- se definió una allowlist de raíz;
- se definieron destinos para scripts de auditoría, experimentos, smoke, notebooks y outputs;
- se documentó una estructura física objetivo;
- se reforzó que Wyckoff permanece integrado al motor/proyecto;
- se separó explícitamente infraestructura IA de entrenamiento;
- se prohibió crear nuevos scripts experimentales en la raíz.

## Decisión de seguridad

No se movieron scripts activos de raíz porque una migración remota sin grep,
Graphify, imports y suite local podría romper consumidores o comandos
documentados. Esa migración se realizará sobre una carpeta local nueva y
ordenada, conservando el checkout actual como referencia.

## Estado

READY_FOR_LOCAL_CLEAN_COPY
