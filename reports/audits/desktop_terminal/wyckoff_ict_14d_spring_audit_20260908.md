# Auditoría histórica ICT/Wyckoff + Spring/Test — 14 días

**Alcance:** EURUSD, velas M15 cerradas de MT5, 2026-08-25 08:48 a
2026-09-08 08:48 hora de Guayaquil. Solo lectura; no se enviaron órdenes.

## Método

Se reconstruyó una propuesta de entrada anticipada: rango móvil de 32 velas
M15, barrido por debajo del soporte y cierre de recuperación dentro del rango
(Spring/Test), sesiones 08:00–12:00 locales de Londres y Nueva York con
`ZoneInfo`, estocástico 14,3,3 y ventana futura de ocho velas para MFE/MAE.
El objetivo de 10 pips es una métrica de comparación, no un objetivo operativo.

Esta corrida es un **proxy de Spring**. No es una reproducción completa del
motor ICT/Wyckoff por vela: los snapshots históricos de probabilidad y
confirmación no están materializados para cada instante. No se debe confundir
un candidato favorable con una entrada validada.

## Resultado

| Métrica | Resultado |
|---|---:|
| Velas M15 cerradas | 1,592 |
| Candidatos Spring/Test | 8 |
| Con cruce estocástico M15 simultáneo | 3 |
| Alcanzaron +10 pips en 8 velas | 0 |
| Sesiones | Londres y Nueva York |

Los ocho candidatos tuvieron MFE entre 0.5 y 9.0 pips. Algunos presentaron
MAE de 13–15 pips y uno 14.6 pips; por tanto, la entrada anticipada sin una
invalidación estrecha no mejora automáticamente el riesgo. El candidato más
favorable fue 2026-09-02 02:00 Guayaquil (MFE 9.0, MAE 2.1), pero no tuvo el
cruce estocástico simultáneo exigido.

## Lectura

La idea es técnicamente viable como **probe** separado: la zona prevista puede
activar una observación de Spring/Test antes del desplazamiento. En esta muestra
pequeña no hay evidencia para habilitarla directamente: cero de ocho alcanzó
10 pips en la ventana corta y solo tres coincidieron con el estocástico.
El resultado no mide edge ni sustituye un replay ICT/Wyckoff completo.

## Mejora propuesta

1. Congelar diariamente zona, rango y dirección HTF antes de cada sesión.
2. Deduplicar Springs por episodio, no por vela.
3. Permitir probe solo con barrido, cierre dentro del rango y riesgo definido.
4. Añadir confirmación ICT M15 para la segunda entrada; no perseguir la vela.
5. Registrar MFE, MAE, tiempo a confirmación, invalidación y resultado neto.
6. Repetir en meses independientes antes de cambiar el bot o autorizar órdenes.

El bot DEMO permanece en `WAIT_SIGNAL`; esta auditoría no produce snapshot ni
autoriza una operación.
