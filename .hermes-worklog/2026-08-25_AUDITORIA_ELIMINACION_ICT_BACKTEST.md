# Auditoría — eliminación de ict_backtest

AGENTE: Codex
DEPARTAMENTO: D0/D2/D5/D7
TAREA: Auditar dependencias antes de eliminar ict_backtest y proteger el motor,
la lectura diaria, funnel y protocolos de uso futuro.
STATUS: COMPLETED

## Resultado

La carpeta ict_backtest/ ya estaba eliminada en Git por 425fb53. El checkout
actual no contiene la carpeta y no tiene imports Python activos hacia ella.
La evidencia histórica confirma que era un consumidor desechable del motor,
no una dependencia del motor.

## Verificación

- Motor: engine/ permanece como fuente canónica de decisiones.
- Visor nuevo: backtest/ es el consumidor aislado del replay causal.
- Lectura diaria: scripts/daily/ y scripts/opening_readiness.py no dependen del
  backtest histórico.
- Funnel y auditoría: audits/codigo/ y scripts/audit/ consumen engine/ y sus
  contratos actuales.
- Protocolos: las referencias operativas obsoletas fueron actualizadas;
  evidencia histórica fue preservada.

No se eliminó ningún archivo en esta misión porque el objetivo ya estaba
cumplido. No se tocaron datos parquet, gráficos ni otros cambios preexistentes.
