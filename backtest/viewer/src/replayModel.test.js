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

function fixtureV12() {
  const base = fixture();
  const marketState = base.candles.map((candle) => ({
    decision_time: candle.bar_close_time,
    authority_tf: "H1",
    entities: candle.index === 1 ? [{ id: "fvg-1", type: "FVG", origin_tf: "H1", state: "ACTIVE", zone_high: 2, zone_low: 1.5, tradable_time: candle.bar_close_time }] : [],
    terminal_entities: [],
    delta: { created: [], transitioned: [], terminal: [] },
  }));
  const setups = base.candles.map((candle) => ({
    id: `SETUP_${candle.index}`,
    decision_time: candle.bar_close_time,
    authority_tf: "H1",
    direction: null,
    cadena_htf_ltf: ["D1", "H4", "H1", "M15"],
    estado: candle.index >= 2 ? "SETUP_READY" : "WAIT_D1",
    active_tf: "M15",
    condiciones_presentes: candle.index >= 2 ? ["D1 context", "H4 POI"] : [],
    condiciones_faltantes: candle.index >= 2 ? [] : ["D1 context"],
    invalidacion: [],
    evidence_refs: [],
    policy: "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
  }));
  return { ...base, schema_version: "1.2", market_state: marketState, setups };
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
    assert.throws(() => validateArtifact({ ...fixture(), schema_version: "1.0" }), /1.1 o 1.2/);
    assert.throws(() => validateArtifact({ ...fixture(), policy: { ...fixture().policy, can_trade: true } }), /no-trading/);
  });

  it("accepts schema 1.2 and exposes the current market state and setup", () => {
    const artifact = validateArtifact(fixtureV12());
    const visible = visibleReplay(artifact, 2);
    assert.equal(visible.marketState.decision_time, artifact.candles[2].bar_close_time);
    assert.equal(visible.setup.estado, "SETUP_READY");
    assert.deepEqual(visible.setup.condiciones_presentes, ["D1 context", "H4 POI"]);
  });

  it("rejects schema 1.2 without market_state or setups", () => {
    assert.throws(() => validateArtifact({ ...fixture(), schema_version: "1.2" }), /market_state/);
    assert.throws(
      () => validateArtifact({ ...fixtureV12(), setups: fixtureV12().setups.slice(0, 2) }),
      /una entrada por vela visible/,
    );
  });

  it("keeps 1.1 retrocompatibility (no market_state/setups required)", () => {
    const visible = visibleReplay(validateArtifact(fixture()), 1);
    assert.equal(visible.marketState, null);
    assert.equal(visible.setup, null);
  });
});
