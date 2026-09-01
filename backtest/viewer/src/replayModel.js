const SAFE_POLICY = Object.freeze({
  diagnostic_only: true,
  entry_authorized: false,
  can_trade: false,
  can_train: false,
  promotion_authorized: false,
});

const HISTORICAL = new Set(["1.1", "1.2"]);

export function validateArtifact(value) {
  if (!value || typeof value !== "object") throw new Error("El archivo no contiene un objeto JSON.");
  if (HISTORICAL.has(value.schema_version)) return validateHistorical(value);
  if (value.schema_version !== "2.0" || value.artifact_kind !== "MTF_REPLAY") {
    throw new Error(`Schema no compatible: ${value.schema_version ?? "ausente"}.`);
  }
  for (const [key, expected] of Object.entries(SAFE_POLICY)) {
    if (value.policy?.[key] !== expected) throw new Error(`Política insegura: ${key}.`);
  }
  for (const key of ["timeline", "state_deltas", "setups", "episodes", "invalidations", "trades", "rejections"]) {
    if (!Array.isArray(value[key])) throw new Error(`Falta la colección ${key}.`);
  }
  if (!value.candles_by_tf || typeof value.candles_by_tf !== "object") throw new Error("Falta candles_by_tf.");
  return value;
}

function validateHistorical(value) {
  for (const key of ["candles", "timeline", "structure_events", "wyckoff_events", "trades"]) {
    if (!Array.isArray(value[key])) throw new Error(`Histórico incompleto: ${key}.`);
  }
  return { ...value, compatibility_mode: `HISTORICAL_${value.schema_version}` };
}

function atOrBefore(rows, time) {
  const target = new Date(time).getTime();
  return rows.filter((row) => new Date(row.observation_time).getTime() <= target);
}

export function visibleReplay(artifact, cursor) {
  const bounded = Math.max(0, Math.min(cursor, artifact.timeline.length - 1));
  if (artifact.schema_version !== "2.0") return visibleHistorical(artifact, bounded);
  const tick = artifact.timeline[bounded];
  const time = tick.observation_time;
  const candlesByTf = Object.fromEntries(
    Object.entries(artifact.candles_by_tf).map(([tf, rows]) => [tf, atOrBefore(rows, time)]),
  );
  const trades = atOrBefore(artifact.trades, time).map((trade) => {
    if (!trade.result_observation_time || new Date(trade.result_observation_time) <= new Date(time)) return trade;
    return { ...trade, outcome: "PENDING", exit_bar: null, exit_r: null, result_observation_time: null };
  });
  return {
    cursor: bounded,
    tick,
    time,
    candlesByTf,
    stateDeltas: atOrBefore(artifact.state_deltas, time),
    setups: atOrBefore(artifact.setups, time),
    episodes: atOrBefore(artifact.episodes, time),
    invalidations: atOrBefore(artifact.invalidations, time),
    trades,
    rejections: atOrBefore(artifact.rejections, time),
  };
}

function visibleHistorical(artifact, cursor) {
  const candles = artifact.candles.slice(0, cursor + 1);
  return {
    cursor,
    tick: artifact.timeline[cursor],
    time: artifact.timeline[cursor]?.decision_time,
    candlesByTf: { [artifact.timeframe ?? "LEGACY"]: candles },
    stateDeltas: [],
    setups: artifact.setups?.slice(0, cursor + 1) ?? [],
    episodes: [],
    invalidations: [],
    trades: artifact.trades.filter((trade) => trade.entry_index <= cursor),
    rejections: [],
  };
}

export async function loadChunk(manifest, chunkId, fetcher = fetch) {
  const chunk = manifest.chunks.find((item) => item.id === chunkId);
  if (!chunk) throw new Error(`Chunk desconocido: ${chunkId}`);
  const response = await fetcher(chunk.path);
  if (!response.ok) throw new Error(`No se pudo cargar ${chunk.path}`);
  return response.json();
}
