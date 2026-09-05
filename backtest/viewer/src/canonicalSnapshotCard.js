const READY_BRIDGE = "READY_MT5_CLOSED_ONLY";
const OBSERVE_ONLY_POLICY = "OBSERVE_ONLY_NO_ORDER";
const MICRO_TFS = ["M5", "M1"];

function record(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function directionLabel(value) {
  if (value === 1 || value === "1" || value === "BULLISH") return "ALCISTA";
  if (value === -1 || value === "-1" || value === "BEARISH") return "BAJISTA";
  return "SIN DIRECCIÓN PUBLICADA";
}

function hasPublishedDirection(value) {
  return value === 1 || value === "1" || value === "BULLISH" || value === -1 || value === "-1" || value === "BEARISH";
}

function zoneSummary(zone, tf) {
  const value = record(zone);
  return {
    id: String(value.id ?? "ZONA SIN ID"),
    tf: String(value.authority_tf ?? value.origin_tf ?? tf),
    type: String(value.type ?? "ZONA"),
    direction: directionLabel(value.direction),
    state: String(value.state ?? value.status ?? "SIN ESTADO"),
    low: value.zone_low ?? value.low ?? null,
    high: value.zone_high ?? value.high ?? null,
  };
}

function bosLabel(value) {
  if (value === 1 || value === "1") return "BOS ALCISTA";
  if (value === -1 || value === "-1") return "BOS BAJISTA";
  return "SIN BOS PUBLICADO";
}

function microStructure(snapshot, tf) {
  const layer = record(record(snapshot.micro_structure)[tf]);
  const contextLayer = record(record(record(snapshot.context_state).layers)[tf]);
  const source = Object.keys(layer).length ? layer : contextLayer;
  if (!Object.keys(source).length || source.available === false) {
    return { tf, available: false, contextBos: "NO PUBLICADO", microBos: "NO PUBLICADO", trend: "NO PUBLICADO", time: null };
  }
  return {
    tf,
    available: true,
    contextBos: Object.keys(contextLayer).length ? bosLabel(contextLayer.last_bos_direction) : "NO PUBLICADO",
    microBos: bosLabel(source.bos_dir ?? source.last_bos_direction),
    trend: directionLabel(source.trend ?? source.structure_bias),
    time: source.time ?? source.asof_time ?? null,
  };
}

function microConfirmation(snapshot) {
  const value = record(snapshot.micro_confirmation);
  const detail = record(value.detail);
  const byTf = Object.fromEntries(MICRO_TFS.map((tf) => [tf, String(detail[tf] ?? "unavailable").toUpperCase()]));
  return {
    available: value.available === true,
    confirmed: value.confirmed === true,
    detail: byTf,
  };
}

function contextBos(snapshot) {
  return Object.entries(record(record(snapshot.context_state).layers)).flatMap(([tf, layer]) => {
    const value = record(layer);
    if (value.last_bos_bar === null || value.last_bos_bar === undefined) return [];
    return [{ tf, bos: bosLabel(value.last_bos_direction), bar: value.last_bos_bar, time: value.asof_time ?? null }];
  });
}

function abstention(reason, bridgeStatus) {
  return {
    state: "ABSTENCIÓN EXPLÍCITA",
    reason,
    bridgeStatus: bridgeStatus ?? "SIN ESTADO",
    context: null,
    zones: [],
    contextBos: [],
    micro: MICRO_TFS.map((tf) => ({ tf, available: false, contextBos: "NO PUBLICADO", microBos: "NO PUBLICADO", trend: "NO PUBLICADO", time: null })),
    confirmation: { available: false, confirmed: false, detail: Object.fromEntries(MICRO_TFS.map((tf) => [tf, "UNAVAILABLE"])) },
    canTrade: false,
  };
}

// Presentation-only projection. It never inspects OHLC or infers a signal.
export function canonicalSnapshotCard(artifact, bridgeStatus, observedTime = null) {
  if (bridgeStatus !== READY_BRIDGE) {
    return abstention("El bridge no confirma velas MT5 cerradas; se oculta cualquier snapshot anterior.", bridgeStatus);
  }
  const snapshot = record(record(artifact).engine_snapshot);
  if (snapshot.schema_version !== "MT5_OPERATIONAL_SNAPSHOT_V1") {
    return abstention("No hay snapshot canónico MT5 disponible.", bridgeStatus);
  }
  if (snapshot.status !== "READY") {
    return abstention(`Snapshot canónico no listo: ${snapshot.status ?? "SIN ESTADO"}.`, bridgeStatus);
  }
  const artifactPolicy = record(record(artifact).policy);
  if (
    snapshot.policy !== OBSERVE_ONLY_POLICY
    || snapshot.entry_authorized !== false
    || snapshot.can_trade !== false
    || artifactPolicy.diagnostic_only !== true
    || artifactPolicy.entry_authorized !== false
    || artifactPolicy.can_trade !== false
    || artifactPolicy.can_train !== false
    || artifactPolicy.promotion_authorized !== false
  ) {
    return abstention("La política del snapshot no conserva la lectura observacional segura.", bridgeStatus);
  }
  if (!observedTime || new Date(observedTime).getTime() !== new Date(snapshot.decision_time).getTime()) {
    return abstention("El cursor no coincide con el decision_time del snapshot canónico; se ocultan campos futuros.", bridgeStatus);
  }

  const contextState = record(snapshot.context_state);
  const constraints = record(contextState.constraints);
  if (contextState.policy !== "CONTEXT_STATE_NOT_ENTRY_SIGNAL" || constraints.policy !== "CONTEXT_ONLY_NOT_ENTRY") {
    return abstention("La política de Context State no conserva su frontera de solo contexto.", bridgeStatus);
  }
  const zones = Object.entries(record(snapshot.canonical_zones)).flatMap(([tf, values]) => (
    Array.isArray(values) ? values.map((zone) => zoneSummary(zone, tf)) : []
  ));
  const confirmation = microConfirmation(snapshot);
  const micro = MICRO_TFS.map((tf) => microStructure(snapshot, tf));
  const publishedContextBos = contextBos(snapshot);
  const hasPublishedConfirmation = confirmation.available && confirmation.confirmed;
  const directionPublished = hasPublishedDirection(constraints.direction_hint);
  const microAvailable = micro.every((item) => item.available);
  const contextReady = contextState.status === "OK";
  const allowSide = constraints.direction_hint === 1 || constraints.direction_hint === "1" || constraints.direction_hint === "BULLISH"
    ? constraints.allow_long
    : constraints.allow_short;
  const sideAllowed = allowSide === true || allowSide === null;

  return {
    state: hasPublishedConfirmation && directionPublished && microAvailable && contextReady && sideAllowed ? "LECTURA DIAGNÓSTICA" : "ABSTENCIÓN EXPLÍCITA",
    reason: !contextReady
      ? `Context State no está listo: ${contextState.status ?? "NO PUBLICADO"}.`
      : !directionPublished
      ? "Context State no publica dirección; el visor se abstiene."
      : !sideAllowed
        ? "Context State no permite el lado publicado; el visor se abstiene."
      : !microAvailable
        ? "La estructura M5/M1 no está publicada por el snapshot canónico; el visor se abstiene."
      : hasPublishedConfirmation
      ? "Confirmación M5/M1 publicada por el motor; permanece diagnóstico y sin autorización de trading."
      : "No hay confirmación M5/M1 publicada por el motor; no se infiere desde OHLC.",
    bridgeStatus,
    decisionTime: snapshot.decision_time,
    context: {
      status: String(contextState.status ?? "NO PUBLICADO"),
      direction: directionLabel(constraints.direction_hint),
      allowLong: constraints.allow_long,
      allowShort: constraints.allow_short,
    },
    zones,
    contextBos: publishedContextBos,
    micro,
    confirmation,
    canTrade: false,
  };
}
