# Plan ICT Multimodelo Intradia v1

**Estado:** `WORKING`
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
