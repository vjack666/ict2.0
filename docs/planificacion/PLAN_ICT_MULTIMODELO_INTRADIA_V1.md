# Plan ICT Multimodelo Intradia v1

**Estado:** `WORKING — BACKTEST_DIAGNOSTIC_CONNECTED`
**Fecha:** 2026-09-16
**Autoridad:** investigacion local sobre datos existentes; `can_trade=false`; `entry_authorized=false`.

## Objetivo

Medir, sin relajar reglas para alcanzar una cifra, si una poblacion de candidatos
ICT puede clasificarse de forma determinista como PO3, Turtle Soup o Silver
Bullet. La frecuencia se mide contra semanas calendario y se separa del edge.
La IA solo se considera despues de que exista una poblacion determinista,
causal, deduplicada y trazable por familia.

## Inventario de Fase 0

| Elemento | Estado | Decision |
| --- | --- | --- |
| `docs/ict/08_POWER_OF_THREE.md` y `engine/po3.py` | Existe, parcial | Reutilizar como contrato y detector PO3. |
| `docs/ict/06_TURTLE_SOUP.md` y `engine/turtle_soup.py` | Existe, parcial | Reutilizar; separar su medicion de la gramatica generica. |
| `docs/ict/07_SILVER_BULLET.md` y `engine/silver_bullet.py` | Existe, parcial | Reutilizar despues de cerrar el reloj de killzone. |
| `docs/ict/01_KILLZONES.md`, `engine/killzone.py`, `detectors/killzones.py` | Contradictorio | Una ruta usa UTC fijo y otra ET con DST; no certificar Silver Bullet hasta una sola semantica UTC. |
| `docs/contratos/SETUP_GRAMMAR_SUPERVISION_V1.md` | Existe | Mantener para supervision generica; no usar como generador de frecuencia. |
| `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md` | Existe | Mantener como gate economico posterior al gate de frecuencia. |
| `execution_calibration_preflight_v2.py` | Incompleto al inicio | Ampliado para fuente declarada, ventanas causales y salida JSON/MD. |
| `FREQ_GATE_2_3_WEEKLY` | No existe | Crear como contrato nuevo, sin condicion de optimizacion. |
| Contrato de candidato multimodelo | No existe | Crear solo como interfaz comun; no duplica los contratos de estrategia. |

Actualización 2026-09-22: Misión 7 conectó PO3, Turtle Soup y Silver Bullet al
backtest six-TF forense como clasificación diagnóstica por episodio. El cableado
funciona, pero PO3 aparece demasiado amplio y Silver/Turtle no aparecieron
completos en la ventana semanal validada. El plan sigue en calibración; no hay
edge ni autorización operativa.

Las referencias de gobierno a `docs/specs/SDD_GOVERNANCE.md` apuntan a una
ruta ausente. Es deuda documental transversal y no constituye autorizacion
para inventar reglas de estrategia; se registra como `OBSOLETE_REFERENCE`.

## Secuencia de trabajo

1. Cerrar `EXECUTION_CALIBRATION_PREFLIGHT_V2` con hashes, fuente declarada,
   ventanas 4/30/50/100, causalidad y reporte por split.
2. Unificar el reloj de killzone en UTC con conversión ET por `ZoneInfo`, DST
   y pruebas en invierno/verano antes de contar Silver Bullet.
3. Crear una clasificacion paralela, sin tocar `grammar_labels`, para las 286
   filas `ABSTAIN` y `REJECT`. Cada resultado debe explicar familia, gates y
   evidencia ausente; una ausencia de evidencia nunca se cuenta como rechazo
   teorico de la familia.
4. Implementar un generador comun bajo contrato, reutilizando detectores de
   contexto, liquidez, sweep, estructura, displacement, FVG/OB y killzone.
   Las familias son salidas separadas, no tres motores inconexos.
5. Materializar candidatos con lineage, deduplicar el mismo evento economico
   antes del conteo y ejecutar `FREQ_GATE_2_3_WEEKLY` por familia, split,
   mes, ano, sesion, direccion y simbolo.
6. Solo para candidatos estructuralmente validos, usar `fine_execution()`
   como profesor offline y registrar geometria, ancla de sweep y razones de
   fallo. Esto no es fill ni PnL.
7. Si hay poblacion suficiente, aplicar el preregistro `PASS_EDGE_INTRADIA`
   sin optimizar sobre OOS. Si no la hay, informar el resultado cientifico.
8. Solo despues de los pasos anteriores disenar el dataset de IA condicionado
   por `strategy_family` y sus condiciones explicitas.

## Resultado diagnóstico Misión 7

Ventana: 2022-03-07..2022-03-13, EURUSD local.

- `PASS_DIAGNOSTIC` técnico.
- 121 episodios.
- Forense: PASS 121/121.
- PO3 completo: 121.
- Silver Bullet completo: 0.
- Turtle Soup completo: 0.
- IA shadow: `ACEPTAR_ANALISIS=40`, `ABSTENERSE=81`.
- Resultado aceptado: 16 TP, 24 SL, `mean_net_R=-0.4300`.

Interpretación:

- El cableado multimodelo ya existe en el backtest.
- El filtro PO3 debe endurecerse para no contar como protocolo completo toda
  secuencia causal compatible.
- Silver/Turtle requieren revisar mapeo de sweep, reversión, retest y killzone
  antes de concluir que no existen oportunidades.
- El siguiente objetivo sigue siendo 2–3 oportunidades/semana como meta de
  calibración, no permiso operativo.

## Gates de detencion

- `BLOCKED_BY_PROVENANCE`: fuente, tiempo, hash o join temporal no verificable.
- `MORE_DETERMINISTIC_WORK_REQUIRED`: faltan detectores, identidad o
  deduplicacion para medir familias.
- `INSUFFICIENT_FREQUENCY`: la poblacion natural no alcanza la meta; no se
  ajustan reglas solo para elevar el conteo.
- `INSUFFICIENT_EDGE`: hay frecuencia, pero `PASS_EDGE_INTRADIA` no acredita
  edge OOS con costes.
- `READY_FOR_CONDITIONED_AI`: solo tras identidad, causalidad, frecuencia,
  ejecucion diagnostica y contrato de datos completos.

## Reglas invariantes

- La salida es local y diagnostica; no genera ordenes, sugerencias operativas
  ni cambios de autoridad.
- `can_trade=false` y `entry_authorized=false` son campos obligatorios de
  todo artefacto generado.
- Las labels de `setup_grammar_v1` no se sobrescriben durante la auditoria
  multimodelo. La clasificacion paralela tiene schema y hash propios.
- Un candidato que satisfaga mas de una familia conserva todas sus familias,
  pero solo cuenta una vez como evento economico en la frecuencia combinada.

## Enmienda: ejecucion autonoma por perfiles Hermes

**Autoridad:** solicitud de Ruben de 2026-09-16. Forge conserva la coordinacion
operativa de los perfiles existentes; Codex verifica la entrega. No crear otros
bots ni sustituirlos por agentes Codex. `forgue` corresponde al perfil `forge`.
Tablero dedicado: `ict-temporal-v1`. Asignaciones ejecutables:
`docs/planificacion/ICT_TEMPORAL_HERMES_TASKS_V1.json`.

### Correcciones de alcance

- Las 292 filas seleccionadas NO permiten estimar frecuencia natural semanal.
  Los conteos previos de familias son exploratorios, no certificaciones.
- La inspeccion de setup_quality_v1 descrita en esta conversacion indica un
  vector estatico de 36 features; Helix debe reproducirlo y medir dependencia
  real del orden, duracion e historia. No asumir aprendizaje temporal por
  incluir indicadores o nombres de temporalidades.
- `timestamp <= decision_time` no demuestra causalidad por si solo: distinguir
  apertura, cierre, formacion, confirmacion y `available_at` de cada evidencia.
- La enmienda de 2026-09-11 permite entrenamiento exploratorio sin PASS_EDGE.
  El paso 8 anterior condiciona certificacion, no bloquea experimentos honestos.
- No persistir ni regenerar corpus, etiquetas, splits o manifiestos bajo esta
  autorizacion. Desarrollar lectores y transformaciones en memoria; escribir
  solo codigo, modelos y reportes nuevos. Escalar una necesidad de cambiar datos.

### Entregas y responsables

| Perfil real | Departamento | Objetivo y criterio de aceptacion |
| --- | --- | --- |
| forge | D0/D2 | Coordinar tablero, integrar reloj/estado episodico y consumidores; pruebas causales y contratos ejecutables, sin modificar cambios ajenos. |
| nexus | D4 | Inventario real por simbolo/TF/split, hashes, semantica temporal, disponibilidad y huecos; lector continuo en memoria especificado, sin inferir ausencia por un solo loader. |
| orion | D6 | Especificaciones ICT base/PO3/Turtle/Silver: secuencia, espera, invalidacion, sesiones y criterio estadistico preregistrado. No ajustar reglas para cumplir frecuencia. |
| helix | D3 | Auditar tensor real y entrenar baseline/temporal pequeno cuando exista soporte; demostrar aprendizaje temporal incremental o informar insuficiencia. |
| probe | D6 | Replay continuo reproducible, calendario completo, eventos deduplicados, ejecucion y costes; resultados por familia y split con incertidumbre. |
| vigil | D5 | Reproducir de forma independiente causalidad, splits, ablations y metricas; emitir PASS/REVIEW/FAIL con hallazgos, no corregir su propia evidencia. |
| sentinel | D0/D5 | Evaluar limites, alcance y suficiencia de gates; ninguna facultad para habilitar trading. |
| ledger | D1 | Trazabilidad de requisitos a codigo/test/artefacto/run/commit; bitacora consolidada y pendientes. No sustituye auditoria. |

### Camino tecnico y dependencias

1. Nexus y Orion descubren fuentes y contratos en paralelo; Helix audita el
   tensor existente en paralelo. Todos entregan evidencia, no solo propuestas.
2. Forge implementa tras esas entregas: H4/H1 contexto, M15 episodio y M5/M1
   solo si existen fuentes verificadas; joins as-of por disponibilidad, barras
   cerradas y DST. Estados de observacion, espera, confirmacion, mitigacion,
   invalidacion y expiracion persisten entre velas. No exigir todo en una vela.
3. Probe recorre periodos completos, incluyendo semanas sin operaciones y
   estados de espera/rechazo; deduplica episodios por identidad economica.
   Reporta candidatos, entradas simuladas y operaciones cerradas por separado.
   Meta de investigacion: 2-3 operaciones intradia por semana en el universo
   congelado, sin promesa ni obligacion de operar cada semana.
4. Helix representa eventos ordenados, deltas temporales, edad, ventanas OHLC
   separadas por TF y mascaras de faltantes. Ajustes solo TRAIN; agrupacion por
   episodio y purga de horizontes solapados en evaluacion en memoria, sin
   cambiar splits persistidos. No usar OOS ya inspeccionado como holdout virgen.
5. Comparar reglas y baseline estatico con modelo temporal pequeno. Pruebas:
   FULL/PREFIX; agregar futuro no cambia pasado; permutar orden o duracion en
   casos semanticamente distintos; quitar HTF/historia; varias semillas,
   calibracion, abstencion e incertidumbre. No exigir reaccion a permutaciones
   irrelevantes ni dar por probado aprendizaje solo por cambiar predicciones.
6. Probe evalua ejecucion offline: fill posterior, spread, comision, slippage,
   anclas sweep/SL, TP, simultaneidad SL/TP, cierre intradia y no doble conteo.
   `fine_execution()` no es evidencia de fill ni rentabilidad. Reportar edge
   neto, drawdown, distribucion semanal y estabilidad con protocolo congelado.
7. Vigil reproduce; Forge corrige hallazgos y vuelve a solicitar auditoria.
   Sentinel revisa limites; Ledger consolida; Forge presenta dictamen final.
8. Shadow en vivo requiere gate operativo propio. Demo y real son fases futuras
   separadas que necesitan autorizacion explicita; esta mision no las inicia.

### Autonomia verificable, no bucle ilimitado

- Cada tarjeta usa `--goal`, checkpoints y criterios de cierre. El bot continua
  inspeccionando, implementando, probando y corrigiendo hasta cumplir su objetivo
  o documentar un bloqueo real. No pide permiso por cada fase autorizada.
- Dependencias se resuelven mediante padres del tablero, no por mensajes que
  el usuario tenga que trasladar. Forge despacha las tarjetas elegibles,
  revisa artefactos y crea ciclos de correccion con dueños explicitos.
- Limites iniciales por intento: 20 turnos, 2 horas, 2 fallos consecutivos.
  Agotar limite NO es COMPLETED; checkpoint y revision del coordinador antes
  de continuar. No reiniciar indefinidamente un error de proveedor o permisos.
- Mismo checkout operativo, sin worktrees. Un escritor por archivo. Codigo
  compartido del motor solo Forge; Helix solo sus scripts/modelos nuevos;
  Probe solo experimentos propios. Cada perfil escribe evidencia en
  `reports/ict_temporal_v1/<perfil>/`. No sobrescribir datasets ni artefactos.
- `engine/execution.py` ya tiene cambios ajenos: leer y trabajar con ellos;
  no revertir, sobrescribir ni incluirlos en commits de esta mision.
- Indice, plan, Graphify y commits son serializados por Forge al integrar,
  nunca `git add .`; Ledger entrega propuesta de consolidacion en su carpeta.
  No push, no ordenes, no cambio de modelo/proveedor ni compras automaticas.
- Cierre obligatorio por tarjeta: AGENTE, DEPARTAMENTO, TAREA, STATUS,
  EVIDENCIA, ARCHIVOS, RIESGOS, SIGUIENTE ACCION. Separar cierre tecnico de
  resultado cientifico. Insuficiencia de datos/edge es resultado legitimo.
- COMPLETED del programa exige entregables auditados o dictamen negativo
  reproducible y pendientes explicitos; no equivale a uso real autorizado.
- Tarjeta creada no significa worker activo: conservar IDs, intentos, logs,
  recibos y estado de dispatcher. Sin scheduler/gateway activo, Forge debe
  verificar y mantener el despacho; si no puede, declarar bloqueo operativo.

### Despacho comprobado

El 2026-09-16 se crearon 11 tarjetas nativas en `ict-temporal-v1`. Primer
despacho: Forge `t_794063cd`, Nexus `t_0b2b2423`, Orion `t_24fddd4f`, con
recibo `spawned` y estado `running`; esto no certifica avance cientifico.
Helix diagnostico `t_929ec9b5` queda listo; dependientes: Forge implementacion
`t_7a8b1ea7`, Probe `t_d76d1b1d`, Helix entrenamiento `t_ed475967`, Vigil
`t_78e52973`, Sentinel `t_44605114`, Ledger `t_4744b39f`, Forge cierre
`t_3676e147`.

Seguimiento del tablero en esta tarea Codex cada 15 minutos:
`supervisar-hermes-ict-temporal`. Notifica cambios significativos, fallos,
bloqueos o cierre; pausa al cierre o bloqueo externo sin trabajo posible.
No sustituye al worker ni garantiza servicio con el host apagado.
Forge bootstrap termina al verificar el arranque y libera su perfil para la
implementacion; Forge final retoma integracion despues de Ledger. Asi no se
bloquea el perfil con un coordinador que espera su propia tarea dependiente.
Logs iniciales: advertencia `Unknown toolsets: a2a`; revisar actividad y
errores reales antes de certificar comunicacion o entrega entre perfiles.
