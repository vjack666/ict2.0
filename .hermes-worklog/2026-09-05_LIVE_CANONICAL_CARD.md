# Visor live — tarjeta canónica de solo lectura

- AGENTE: Codex director; ict_viewer_builder implementación; ict_assurance auditoría independiente.
- DEPARTAMENTO: D2 ingeniería / D7 delivery, con D5 assurance y D1 cierre.
- TAREA: reemplazar escenario fijo de compra por snapshot canónico.
- STATUS: COMPLETED — PASS técnico del cambio, sin certificación de feed o trading.

## Cambio y autoridad

Se elimina ScenarioPanel y sus cálculos de entrada, stop, objetivo, pips y
beneficio. La nueva proyección consume exclusivamente engine_snapshot:
Context State, zonas con identidad/rango, BOS por capa y microestructura M5/M1.
El ensamblador publica micro_structure y micro_confirmation utilizando
build_context_stack y ltf_confirms ya existentes, con dirección de daily_motor.
No introduce detectores ni modifica dirección, reglas o gates del motor.

La tarjeta se abstiene ante falta de confirmación, contexto inválido, política
incompatible, snapshot ausente/bloqueado, corte distinto o bridge no disponible.
La confirmación agregada sigue la semántica canónica; no significa orden ni
que ambos TF confirmen. can_trade=false y entry_authorized=false.

## Evidencia

- Python: 19 PASS en tests/test_mt5_operational_snapshot.py y tests/test_daily_motor.py.
- Igualdad de snapshot FULL/PREFIX en tres cortes sintéticos (horas 2, 4 y 6),
  incluyendo campos micro y filas futuras; transporte canónico y ausencia de datos.
- La .venv local carece de pluggy; se utilizó python del sistema, sin instalar paquetes.
- QA visual root en navegador local puerto 5178: tarjeta UNAVAILABLE legible,
  ABSTENCIÓN EXPLÍCITA y CAN_TRADE=FALSE, sin niveles ficticios.
- Auditoría independiente revisa backend y frontend; hallazgos de Context State
  inválido y BOS de capas superiores corregidos en la misma misión.
- Auditoría independiente final: npm test 10/10 PASS; Vite build PASS (31 módulos);
  git diff --check PASS. Context State conserva null como ausencia de restricción
  y false como lado bloqueado; campo ausente falla cerrado.
- Graphify AST: 12.875 nodos / 21.372 aristas; graph.json y reporte actualizados.
  Avisos preexistentes de archivos sin nodos; HTML omitido por límite de tamaño.
- Autoauditoría: objetivo satisfecho, sin cálculos de niveles; límites y abstención
  verificados. Dictamen D5: TECHNICAL_READY; procedencia sin certificar.

## Archivos y límites

Write set: engine/mt5_operational_snapshot.py, tests/test_mt5_operational_snapshot.py,
backtest/viewer/src/{App.jsx,styles.css,canonicalSnapshotCard.js,canonicalSnapshotCard.test.js},
contrato MT5, SDD del puente y del visor, índice y esta bitácora.
Los cambios previos en datos, informes, gráficos y .atl se preservan fuera del commit.
Graphify se actualiza localmente mediante AST; sus artefactos están ignorados por Git.

## Riesgos y siguiente acción

La inspección visual cubre abstención sin bridge; no certifica frescura de un
feed MT5 activo. No se ejecutó una sesión nueva de mercado, backtest científico,
entrenamiento, orden ni publicación. El cambio técnico no certifica provenance.
El bridge debe cargar el código nuevo para publicar los campos micro; snapshots
antiguos sin ellos se abstienen. Siguiente acción: uso diagnóstico local cuando
exista snapshot fresco, conservando las mismas restricciones.
