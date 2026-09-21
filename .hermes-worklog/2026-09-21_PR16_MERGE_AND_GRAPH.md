# Bitacora — PR #16 merge y grafo de linaje 6-TF

**Fecha:** 2026-09-21  
**PR:** https://github.com/vjack666/ict2.0/pull/16  
**Estado:** `MERGED`  
**Base mergeada:** `hermes/evidencia-ict-replay-pass-20260920`  
**Merge commit remoto:** `d4fdf68def1915ce29f0e3abe31e33f19eeb92ea`  
**HEAD certificado del PR:** `5146055a5c9c94b7933e2b3252372ebd183cdc96`  

## Alcance

Se continuo la certificacion del PR #16 sin crear ramas nuevas. El branch
existente del PR (`chatgpt/full-lineage-gate-20260921`) fue reparado y
actualizado directamente con el commit:

```text
5146055a fix(lineage): certify six-TF anchor gate
```

No se ejecuto MT5, no se conecto broker, no se entreno GRU y `can_trade=false`
permanece vigente.

## Gates ejecutados antes del merge

Suite focal exacta del workflow:

```text
tests/test_phase_d_lineage.py
tests/test_full_sixtf_lineage_gate.py
tests/test_fvg_ob_relations.py
tests/test_historical_event_objects.py
tests/test_setup_builder_integration.py
tests/test_daily_motor.py
tests/test_mt5_operational_snapshot.py
tests/test_causal_replay.py
tests/test_sixtf_causal_sequence_phase1.py
```

Resultado:

```text
83 passed in 9.94s
```

El verificador `scripts/audit/verify_full_sixtf_lineage_gate.py` tambien fue
ejecutado previamente contra `EURUSD.zip` original y manifesto benchmark,
produciendo `all_pass=true`. En esta continuacion no se repitio el ZIP por
instruccion del usuario.

## Resultado GitHub

GitHub reporto:

```text
state=MERGED
mergeable=MERGEABLE
mergeStateStatus=CLEAN
mergeCommit=d4fdf68def1915ce29f0e3abe31e33f19eeb92ea
```

`origin/hermes/evidencia-ict-replay-pass-20260920` quedo en:

```text
d4fdf68def1915ce29f0e3abe31e33f19eeb92ea
```

## Grafo enfocado

Se consulto Graphify en el worktree detached del PR:

```text
graphify path "build_daily_motor_snapshot()" "validate_six_tf_lineage()"
```

Resultado:

```text
build_daily_motor_snapshot() --calls--> validate_six_tf_lineage()
```

Tambien:

```text
graphify path "build_mt5_operational_snapshot()" "validate_six_tf_lineage()"
```

Resultado:

```text
build_mt5_operational_snapshot()
  <--imports-- test_mt5_operational_snapshot.py --imports-->
validate_six_tf_lineage()
```

El grafo completo existe como `graphify-out/graph.json`, pero no se genero
HTML por exceso de tamano (`12877 nodes`, limite visual `5000`).

## Decision

PR #16 queda fusionado. La siguiente accion local debe ser actualizar una rama
operativa concreta solo cuando el usuario indique cual usar, porque el checkout
principal actual contiene cambios locales sucios que no deben sobrescribirse.
