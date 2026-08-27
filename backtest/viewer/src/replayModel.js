export const LAYER_DEFAULTS = Object.freeze({
  SWING: false,
  BOS: true,
  CHOCH: true,
  WYCKOFF: true,
  RANGE: true,
  TRADES: true,
});

export function validateArtifact(value) {
  if (!value || typeof value !== "object") throw new Error("El archivo no contiene un objeto JSON.");
  if (value.schema_version !== "1.1") {
    throw new Error(`Schema no compatible: ${value.schema_version ?? "ausente"}; se requiere 1.1.`);
  }
  for (const key of ["candles", "timeline", "structure_events", "wyckoff_events", "trades"]) {
    if (!Array.isArray(value[key])) throw new Error(`Falta la colección ${key}.`);
  }
  if (!value.candles.length || value.timeline.length !== value.candles.length) {
    throw new Error("Candles y timeline deben tener igual longitud no vacía.");
  }
  if (
    value.policy?.diagnostic_only !== true
    || value.policy?.entry_authorized !== false
    || value.policy?.can_trade !== false
    || value.policy?.can_train !== false
    || value.policy?.promotion_authorized !== false
  ) {
    throw new Error("El artefacto no cumple la política diagnóstica/no-trading.");
  }
  value.candles.forEach((candle, index) => {
    if (candle.index !== index || value.timeline[index]?.index !== index) {
      throw new Error("Índices visibles no contiguos.");
    }
    if (value.timeline[index].decision_time !== candle.bar_close_time) {
      throw new Error(`decision_time no coincide con el cierre en la vela ${index}.`);
    }
  });
  return value;
}

export function visibleReplay(artifact, cursor, layers = LAYER_DEFAULTS) {
  const bounded = Math.max(0, Math.min(cursor, artifact.candles.length - 1));
  const candles = artifact.candles.slice(0, bounded + 1);
  const structureEvents = artifact.structure_events.filter(
    (event) => event.confirmed_index <= bounded && layers[event.kind] !== false,
  );
  const wyckoffEvents = layers.WYCKOFF === false
    ? []
    : artifact.wyckoff_events.filter((event) => event.first_seen_index <= bounded);
  const trades = layers.TRADES === false
    ? []
    : artifact.trades
      .filter((trade) => trade.entry_index <= bounded)
      .map((trade) => (
        trade.result_confirmed_index != null && trade.result_confirmed_index <= bounded
          ? trade
          : {
              ...trade,
              exit_index: null,
              exit_time: null,
              exit_price: null,
              outcome: "PENDING",
              exit_r: null,
              bars_held: null,
              result_confirmed_index: null,
            }
      ));
  return {
    cursor: bounded,
    candle: artifact.candles[bounded],
    point: artifact.timeline[bounded],
    candles,
    structureEvents,
    wyckoffEvents,
    trades,
  };
}

export function chartTime(raw) {
  return Math.floor(new Date(raw).getTime() / 1000);
}

export function toLocalInput(raw) {
  return new Date(raw).toISOString().slice(0, 16);
}

export function cursorAtOrBefore(candles, localValue) {
  const target = new Date(`${localValue}:00Z`).getTime();
  let found = 0;
  candles.forEach((candle, index) => {
    if (new Date(candle.bar_close_time).getTime() <= target) found = index;
  });
  return found;
}
