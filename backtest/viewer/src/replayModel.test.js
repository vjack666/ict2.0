import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { loadChunk, validateArtifact, visibleReplay } from "./replayModel.js";

function fixture() {
  const times = ["2024-01-01T04:00:00Z", "2024-01-01T04:15:00Z", "2024-01-01T04:30:00Z"];
  const rows = times.map((observation_time, index) => ({ index, tf: "M15", observation_time, open: 1, high: 2, low: 0, close: 1 }));
  return {
    schema_version: "2.0",
    artifact_kind: "MTF_REPLAY",
    policy: { diagnostic_only: true, entry_authorized: false, can_trade: false, can_train: false, promotion_authorized: false },
    candles_by_tf: { M15: rows },
    timeline: times.map((observation_time, index) => ({ id: `T${index}`, index, observation_time })),
    state_deltas: [{ id: "past", observation_time: times[0] }, { id: "future-secret", observation_time: times[2] }],
    setups: [{ id: "setup", observation_time: times[0] }],
    episodes: [{ id: "episode", observation_time: times[1] }],
    invalidations: [{ id: "invalid", observation_time: times[2] }],
    trades: [{ id: "trade", observation_time: times[0], outcome: "TP", result_observation_time: times[2], exit_r: 3 }],
    rejections: [],
  };
}

describe("MTF causal viewer", () => {
  it("never exposes T+1 and masks future trade outcome", () => {
    const visible = visibleReplay(validateArtifact(fixture()), 1);
    assert.equal(JSON.stringify(visible).includes("future-secret"), false);
    assert.equal(visible.invalidations.length, 0);
    assert.equal(visible.trades[0].outcome, "PENDING");
    assert.equal(visible.candlesByTf.M15.length, 2);
  });

  it("rejects unsafe policy", () => {
    const unsafe = fixture();
    unsafe.policy.can_trade = true;
    assert.throws(() => validateArtifact(unsafe), /Política insegura/);
  });

  it("loads only the requested chunk", async () => {
    const calls = [];
    const data = await loadChunk({ chunks: [{ id: "C1", path: "/one.json" }] }, "C1", async (path) => {
      calls.push(path);
      return { ok: true, json: async () => ({ id: "C1" }) };
    });
    assert.deepEqual(calls, ["/one.json"]);
    assert.equal(data.id, "C1");
  });
});
