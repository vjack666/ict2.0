import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { validateArtifact, visibleReplay } from "./replayModel.js";

function fixture() {
  const candles = Array.from({ length: 4 }, (_, index) => ({
    index,
    bar_open_time: `2024-01-01T0${index}:00:00+00:00`,
    bar_close_time: `2024-01-01T0${index + 1}:00:00+00:00`,
    open: 1 + index, high: 2 + index, low: 0.5 + index, close: 1.5 + index,
  }));
  return {
    schema_version: "1.1",
    policy: {
      diagnostic_only: true,
      entry_authorized: false,
      can_trade: false,
      can_train: false,
      promotion_authorized: false,
    },
    candles,
    timeline: candles.map((candle) => ({ index: candle.index, decision_time: candle.bar_close_time })),
    structure_events: [{ id: "past", kind: "BOS", confirmed_index: 1 }, { id: "future-secret", kind: "BOS", confirmed_index: 3 }],
    wyckoff_events: [{ id: "wy-past", first_seen_index: 1 }, { id: "wy-future-secret", first_seen_index: 3 }],
    trades: [{ id: "trade", entry_index: 1, result_confirmed_index: 3, outcome: "TP", exit_time: "future-secret", exit_r: 2 }],
  };
}

describe("causal viewer model", () => {
  it("delivers exactly cursor+1 candles and no future entities", () => {
    const visible = visibleReplay(validateArtifact(fixture()), 1);
    assert.equal(visible.candles.length, 2);
    assert.equal(JSON.stringify(visible).includes("future-secret"), false);
    assert.deepEqual(visible.structureEvents.map((event) => event.id), ["past"]);
    assert.deepEqual(visible.wyckoffEvents.map((event) => event.id), ["wy-past"]);
    assert.equal(visible.trades[0].outcome, "PENDING");
  });

  it("rejects v1.0 and unsafe policy flags", () => {
    assert.throws(() => validateArtifact({ ...fixture(), schema_version: "1.0" }), /1.1/);
    assert.throws(() => validateArtifact({ ...fixture(), policy: { ...fixture().policy, can_trade: true } }), /no-trading/);
  });
});
