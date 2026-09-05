import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { canonicalSnapshotCard } from "./canonicalSnapshotCard.js";

function artifact({ confirmed = false } = {}) {
  return {
    policy: { diagnostic_only: true, entry_authorized: false, can_trade: false, can_train: false, promotion_authorized: false },
    engine_snapshot: {
      schema_version: "MT5_OPERATIONAL_SNAPSHOT_V1",
      status: "READY",
      policy: "OBSERVE_ONLY_NO_ORDER",
      entry_authorized: false,
      can_trade: false,
      decision_time: "2026-09-05T12:00:00Z",
      context_state: {
        status: "OK",
        policy: "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
        constraints: { direction_hint: "BULLISH", allow_long: true, allow_short: false, policy: "CONTEXT_ONLY_NOT_ENTRY" },
        layers: { H1: { last_bos_bar: 14, last_bos_direction: 1, asof_time: "2026-09-05T12:00:00Z" } },
      },
      canonical_zones: { M15: [{ id: "FVG-M15-1", type: "FVG", direction: 1, state: "ACTIVE", origin_tf: "M15" }] },
      micro_structure: {
        M5: { available: true, time: "2026-09-05T12:00:00Z", trend: "BULLISH", bos_dir: 1 },
        M1: { available: true, time: "2026-09-05T12:00:00Z", trend: "RANGING", bos_dir: 0 },
      },
      micro_confirmation: { available: true, confirmed, score: confirmed ? 1 : 0, detail: { M5: "with", M1: "neutral" } },
    },
  };
}

describe("canonical snapshot card", () => {
  it("uses only published canonical fields and abstains without M5/M1 confirmation", () => {
    const card = canonicalSnapshotCard(artifact(), "READY_MT5_CLOSED_ONLY", "2026-09-05T12:00:00Z");
    assert.equal(card.state, "ABSTENCIÓN EXPLÍCITA");
    assert.match(card.reason, /no se infiere desde OHLC/i);
    assert.deepEqual(card.context, { status: "OK", direction: "ALCISTA", allowLong: true, allowShort: false });
    assert.deepEqual(card.zones, [{ id: "FVG-M15-1", tf: "M15", type: "FVG", direction: "ALCISTA", state: "ACTIVE", low: null, high: null }]);
    assert.equal(card.micro[0].microBos, "BOS ALCISTA");
    assert.equal(card.micro[1].microBos, "SIN BOS PUBLICADO");
    assert.deepEqual(card.contextBos, [{ tf: "H1", bos: "BOS ALCISTA", bar: 14, time: "2026-09-05T12:00:00Z" }]);
    assert.deepEqual(card.confirmation.detail, { M5: "WITH", M1: "NEUTRAL" });
    assert.equal(card.canTrade, false);
    assert.equal(/\b(SL|TP|entrada|stop|target)\b/i.test(JSON.stringify(card)), false);
  });

  it("keeps a published confirmation diagnostic-only", () => {
    const card = canonicalSnapshotCard(artifact({ confirmed: true }), "READY_MT5_CLOSED_ONLY", "2026-09-05T12:00:00Z");
    assert.equal(card.state, "LECTURA DIAGNÓSTICA");
    assert.equal(card.confirmation.confirmed, true);
    assert.equal(card.canTrade, false);
  });

  it("withholds a stale snapshot when the bridge is blocked", () => {
    const card = canonicalSnapshotCard(artifact({ confirmed: true }), "BLOCKED", "2026-09-05T12:00:00Z");
    assert.equal(card.state, "ABSTENCIÓN EXPLÍCITA");
    assert.equal(card.context, null);
    assert.deepEqual(card.zones, []);
    assert.match(card.reason, /oculta cualquier snapshot anterior/i);
  });

  it("fails closed when context direction or a microstructure layer is not published", () => {
    const noDirection = artifact({ confirmed: true });
    delete noDirection.engine_snapshot.context_state.constraints.direction_hint;
    assert.equal(canonicalSnapshotCard(noDirection, "READY_MT5_CLOSED_ONLY", "2026-09-05T12:00:00Z").state, "ABSTENCIÓN EXPLÍCITA");

    const noM1 = artifact({ confirmed: true });
    noM1.engine_snapshot.micro_structure.M1.available = false;
    assert.equal(canonicalSnapshotCard(noM1, "READY_MT5_CLOSED_ONLY", "2026-09-05T12:00:00Z").state, "ABSTENCIÓN EXPLÍCITA");
  });

  it("withholds a latest snapshot when the replay cursor is earlier", () => {
    const card = canonicalSnapshotCard(artifact({ confirmed: true }), "READY_MT5_CLOSED_ONLY", "2026-09-05T11:55:00Z");
    assert.equal(card.state, "ABSTENCIÓN EXPLÍCITA");
    assert.equal(card.context, null);
    assert.match(card.reason, /ocultan campos futuros/i);
  });

  it("abstains when Context State is not OK or rejects its published side", () => {
    const incomplete = artifact({ confirmed: true });
    incomplete.engine_snapshot.context_state.status = "INCOMPLETE";
    assert.equal(canonicalSnapshotCard(incomplete, "READY_MT5_CLOSED_ONLY", "2026-09-05T12:00:00Z").state, "ABSTENCIÓN EXPLÍCITA");

    const sideBlocked = artifact({ confirmed: true });
    sideBlocked.engine_snapshot.context_state.constraints.allow_long = false;
    assert.equal(canonicalSnapshotCard(sideBlocked, "READY_MT5_CLOSED_ONLY", "2026-09-05T12:00:00Z").state, "ABSTENCIÓN EXPLÍCITA");
  });

  it("preserves an unconstrained side and rejects a Context State policy drift", () => {
    const unconstrained = artifact({ confirmed: true });
    unconstrained.engine_snapshot.context_state.constraints.allow_long = null;
    assert.equal(canonicalSnapshotCard(unconstrained, "READY_MT5_CLOSED_ONLY", "2026-09-05T12:00:00Z").state, "LECTURA DIAGNÓSTICA");

    const unsafeContext = artifact({ confirmed: true });
    unsafeContext.engine_snapshot.context_state.policy = "ENTRY_SIGNAL";
    assert.equal(canonicalSnapshotCard(unsafeContext, "READY_MT5_CLOSED_ONLY", "2026-09-05T12:00:00Z").state, "ABSTENCIÓN EXPLÍCITA");
  });
});
