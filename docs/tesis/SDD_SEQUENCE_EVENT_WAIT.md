# Espera por eventos en la secuencia canónica

Fecha: 2026-09-05. Dueño: D2 / Codex. Auditoría: D5.
Autorización: el usuario pidió corregir la espera y evitar caducidad arbitraria por conteo de velas.

## Alcance y fundamento

`docs/auditoria/AUDITORIA_TEMPORAL_AHF_MTF.md` exige medir permanencia,
transiciones y retrocesos con causas observables. Ese documento describe la
navegación esperada; no demuestra por sí solo que todas las reglas de la tesis
prohíban cualquier plazo. Esta corrección aplica la decisión explícita del usuario
a `engine.sequence`: esperar confirmación mientras el escenario conserve validez.

## Contrato

- Por defecto no caduca SWEEP, DISPLACE ni la espera de retorno por un número fijo
  o derivado de velas. Un límite entero positivo explícito sigue disponible para
  experimentos acotados y se identifica como tal. No reproduce por sí solo todas
  las reglas de versiones anteriores.
- Cada vela cerrada evalúa el contexto y las reglas de invalidación antes de
  aceptar la siguiente fase. Cambio de dirección, veto de contexto o ruptura de
  un nivel estructural congelado deben conservar un motivo auditable.
- Contexto neutral o ausente suspende la confirmación y conserva la secuencia;
  no equivale a un giro contrario. La ruptura de un nivel ya conocido sigue
  siendo evaluable aunque el contexto esté temporalmente ausente.
- Los niveles se calculan con datos disponibles al nacimiento. No se inventan
  niveles si falta evidencia. La falta de un nivel no autoriza una entrada.
- SWEEP, DISPLACE y BOS conservan orden temporal; esta misión no modifica la
  detección de displacement ni relaja sus requisitos.
- Al acabar un histórico se devuelve el estado pendiente. No se convierte en
  fracaso, señal, resultado económico ni muestra etiquetada para entrenamiento.
- El procesamiento termina después de las velas suministradas. La espera es
  estado guardado entre eventos, no un bucle que consulta continuamente.
- Backtest y funnel transportan el registro del motor sin calcular reglas.
  Un funnel vacío puede conservar la auditoría, pero sigue BLOCKED para episodios.
- `can_trade=false`; sin promoción. No cambia el cálculo de SL/TP.

## Verificación requerida

Confirmación después de seis velas; invalidación antes de confirmar; fin de datos
pendiente; timeout explícito; conservación batch/streaming y prefijos; transporte
del registro al funnel sin generar labels. Ninguna mejora económica se presupone.
