# Plan de trabajo: Contexto causal → evidencia → entrenamiento

- [x] 1. Corregir y probar snapshots D1/H4/H1 point-in-time.
- [x] 2. Ejecutar matriz OOS causal fija: Q2 (ya cerrado), Q3 y Q4 de 2022; EURUSD M15, H200, cola de resolución de 8 días; H4 solo vs D1/H4/H1/M15.
- [x] 3. Medir por perfil, trimestre, dirección y sesión; separar TP, SL y sin resolver; no inferir edge de OPEN.
- [x] 4. Aplicar gate de materialización: solo episodios causales del perfil ganador si hay soporte resuelto y ventaja consistente; si no, declarar BLOCKED y no fabricar corpus.
- [x] 5. Entrenar únicamente si el gate pasa; split temporal, artefacto reproducible, Shadow Mode, `can_trade=false`.

Reglas: sin órdenes, sin promoción, sin push y sin bucles/reintentos. Cada tramo escribe estado y termina.

## Cierre automático
Q2--Q4 terminó. Full context suma 13 señales: 7 resueltas (2 TP, 5 SL) y 6 sin resolver. El mínimo definido es 30 resueltas por perfil; el gate no pasa. No se materializó corpus ni se entrenó, para no convertir evidencia insuficiente en un modelo ficticio.
