# Bitácora — Misión 6 Secuencia real en backtest + caja negra

## Objetivo

Conectar al backtest los módulos secuenciales ya existentes para que los
episodios six-TF no dependan solo de timestamps sintéticos. Añadir caja negra
por episodio para detectar fallos de forma más eficaz.

## Cambios

- `backtest/sixtf_forensic.py` ahora puede adjuntar evidencia de
  `engine.sequential_events.run_sequential`.
- `scripts/audit/run_sixtf_episode_backtest.py` acepta `--sequence-tf` y
  `--blackbox-output`.
- La auditoría acepta un episodio comprimido sintéticamente solo si existe una
  cadena real completa multi-bar anterior a `decision_time`.
- Se añadió caja negra JSONL con política segura (`can_trade=false`).

## Evidencia

Suite focal:

```text
python -m pytest -q tests/test_sixtf_forensic.py tests/test_sixtf_episode_backtest.py tests/test_sequential_events.py
25 passed
```

Backtest marzo 2022 con secuencia real M1:

```text
decision_count=553
episode_count=553
status=PASS_DIAGNOSTIC
forensic PASS=553/553
complete_chain_count=122
blackbox_lines=553
```

Resultado económico total marzo:

```text
TP=153
SL=313
HORIZON=87
win_rate=0.3283
mean_net_R=-0.5733
sum_net_R=-267.18
```

IA shadow después de resolver compresión:

```text
ACEPTAR_ANALISIS=184
ABSTENERSE=369
```

Subconjunto aceptado por IA shadow:

```text
trades=184
TP=69
SL=111
HORIZON=4
win_rate=0.3833
mean_net_R=-0.4633
sum_net_R=-83.40
frecuencia semanal=32,40,40,40,32
```

## Veredicto

El primer problema quedó atacado: el backtest ya puede usar secuencia real M1 y
la caja negra muestra evidencia por episodio. La compresión sintética ya no
bloquea marzo 2022. El siguiente problema es calibración/filtro de calidad:
todavía hay demasiados trades por semana y expectativa negativa.
