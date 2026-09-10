# Mechanical Bot Loop — Audit & Intrabar Adjustment

Use when working on `mechanical_bot/` (service loop, core stochastic, MT5 adapter,
readiness gates, snapshot validation) within ICT SYSTEM.

## Trigger
- Any audit of the mechanical bot loop (`service.py`, `core.py`, `mt5_adapter.py`).
- Any change to stochastic calculation (`crossed_down_from_overbought`, `crossed_up_from_oversold`).
- Any verification of MT5 adapter reliability (`server_utc_offset_seconds`, `closed_m15_candles`, snapshot freshness).

## Always-on rules
- The bot's `stochastic_14_3_3` is a closed-candle stochastic (14,3,3); it requires `len(candles) >= 14+3+3 = 20` before producing a reading.
- `crossed_down_from_overbought(threshold=80)` requires `prev_K >= 80`, `prev_D >= 80`, `prev_K >= prev_D`, `K < D`. Changing this removes the `prev_K >= prev_D` guard and allows intrabar confirmations — document the change in `.hermes-worklog/`.
- `MT5Adapter.closed_m15_candles(symbol, count)` reads `copy_rates_from_pos(symbol, TIMEFRAME_M15, 1, count)` — it skips index 0 (current forming candle). For intrabar readings, use a separate adapter call or change `start`.
- `MT5Adapter` uses `server_utc_offset_seconds` to adjust timestamps in `_assert_recent_epoch`. The default (`0`) is wrong for MetaQuotes-Demo servers that report UTC+3; set `+3*3600` (=10800) in the adapter constructor or via `--server-utc-offset-hours 3`.
- Before asserting a signal failure, verify the adapter's log (`mechanical_bot_events.jsonl`) for `EXECUTION_ERROR`, `SNAPSHOT_INVALID`, or `STOCHASTIC_STALE` rather than assuming the bot missed a tick.
- `manual_direction` (`SELL`/`BUY`) requires both a valid snapshot (`latest_snapshot.json`) and an M15 stochastic cross; without both, the bot stays in `WAIT_MANUAL_DIRECTION_STOCHASTIC`.
- The `mechanical_bot_state.json` does not persist `manual_direction`; check `.hermes-state/mechanical_bot_events.jsonl` for `MANUAL_DIRECTION_SELECTED` to confirm the user's direction selection.

## Procedure for mechanical bot audit (step order)
1. Read `.hermes-state/mechanical_bot_state.json` (current bot state, cycle, manual direction if present).
2. Read `.hermes-state/mechanical_bot_events.jsonl` (last 5 events: ARMED/DECISION/EXECUTION_ERROR/ORDER_REQUEST/ORDER_RESULT).
3. Read `.hermes-worklog/` for the most recent worklog (`.hermes-index.md` for task tracking).
4. Check `mechanical_bot/core.py` for stochastic conditions (`crossed_down_from_overbought`, `crossed_up_from_oversold`) — read before editing.
5. Verify adapter config (`scripts/start_mechanical_bot.py`: `server_utc_offset_seconds`). Confirm it matches the MT5 server's timezone offset.
6. Run adapter smoke test (`python -c` with `MT5Adapter` connecting to the real terminal, reading `closed_m15_candles`, computing `stochastic_14_3_3`). Confirm no `RuntimeError` (`stale/future`) and that `K`/`D` values are fresh (last candle time within 30 min of now).
7. Compare the adapter's last stochastic values with the user's reference (e.g., a photo of the terminal). Note the difference between intrabar (`start=0` or live tick) and closed-candle (`start=1`) calculations.
8. If changing stochastic formula: apply patch to `core.py`, update `.hermes-worklog/` with the reason, and re-run the adapter smoke test with new formula.
9. Report truthfully: state if the adapter is blocked (`age < 0`), if the loop is alive, and whether the user's perceived cross is confirmed by the bot's strict rules or only visible intrabar.
- Never fabricate PASS results; if the adapter is blocked (`RuntimeError`), report BLOCKED.
- Never claim the loop is broken when it is waiting for conditions (`WAIT_MANUAL_DIRECTION_STOCHASTIC` is a valid state, not an error).

## Pitfalls (imperative, with mechanism)
- Adapter `start=1` skips the forming candle → intrabar signals in a photo are NOT confirmed by `stochastic_14_3_3`. Fix: either use `start=0` (separate adapter call) or document the difference explicitly.
- `server_utc_offset_seconds=0` with MT5 server in UTC+offset makes `_assert_recent_epoch` compute negative age (future), blocking all data. Fix: configure adapter with real offset (`+3*3600` for MetaQuotes-Demo observed offset; verify with `timestamp - server_utc_offset_seconds`).
- Changing `crossed_down_from_overbought` to remove `prev_K >= prev_D` allows intrabar confirmation but increases false positives; document the trade-off in the worklog.
- `manual_direction` is lost when `mechanical_bot_state.json` restores after a restart (it is not persisted); check `.hermes-state/mechanical_bot_events.jsonl` for `MANUAL_DIRECTION_SELECTED` events.
- `execution_enabled` must be `True` for `manual_entry` and `tick()` to reach the adapter; if false, the bot stays in `OFF`/`WAIT_SIGNAL` even with valid stochastic cross.
- `cycle` state with `entries >= 1` but `cycle` missing in restored state (`mechanical_bot_state.json`) produces `OWN_POSITIONS_MISSING` in the adapter; the initial `MT5 open failed` (`Unnamed arguments not allowed`) leaves the cycle incomplete and requires manual reconciliation (`close_cycle`).
- The adapter's `execute()` uses `correlation_id` tied to the blackbox; any `BlackBoxWriteError` stops execution (`RuntimeError`). Monitor `.hermes-state/mechanical_bot_blackbox.jsonl` before claiming an order completed.

## References / depth
- `references/user_preferences.md` (user's preference: brief Spanish responses, real verified values — no dashes, no fabricated output, no multiple URLs).
- `references/ict_system_repo_pitfalls.md` (ROOT calculation, shims, venv issues, push evidence).
- Full verification script: use `python -c` importing `MT5Adapter` + `core.stochastic_14_3_3` to read real candles, compute stochastic, and verify adapter state. Save results to `.hermes-worklog/<date>.md` with `git diff --cached --stat` if code changed.
