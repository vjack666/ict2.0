import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  createChart,
  createSeriesMarkers,
} from "lightweight-charts";
import {
  ArrowCounterClockwise,
  CaretLeft,
  CaretRight,
  ChartLine,
  CheckCircle,
  Clock,
  Eye,
  FileArrowUp,
  Flask,
  GitBranch,
  Pause,
  Play,
  ShieldCheck,
  WarningCircle,
} from "@phosphor-icons/react";
import {
  LAYER_DEFAULTS,
  chartTime,
  cursorAtOrBefore,
  toLocalInput,
  validateArtifact,
  visibleReplay,
} from "./replayModel";

const PHASE_TONES = {
  ACCUMULATION: "cyan",
  MARKUP: "green",
  DISTRIBUTION: "violet",
  MARKDOWN: "red",
  TRANSITION: "amber",
  RANGE_UNCLASSIFIED: "slate",
  UNKNOWN: "neutral",
};

const EVENT_COLORS = {
  SWING: "#8793a4",
  BOS: "#62a0ff",
  CHOCH: "#f6b94d",
  SPRING: "#23b8aa",
  UPTHRUST: "#c08cff",
  UTAD: "#d891ff",
  SOS: "#39ca8b",
  SOW: "#ff5d5d",
  LPS: "#76d8bf",
  LPSY: "#ff9090",
  TEST: "#8db8ff",
  FAILED_TEST: "#ff7474",
  RANGE_BREAK: "#f6b94d",
  EFFORT_RESULT_DIVERGENCE: "#d891ff",
};

function formatUtc(raw) {
  if (!raw) return "NO DISPONIBLE";
  return new Intl.DateTimeFormat("es-EC", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    hour12: false, timeZone: "UTC",
  }).format(new Date(raw));
}

function formatPrice(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(5) : "—";
}

// Persistent-region types that carry a price zone (FVG/OB/Breaker/BPR).
const REGION_TYPES = new Set(["FVG", "ORDER_BLOCK", "BREAKER", "BPR"]);

// Map an entity's activation time to the visible candle index whose close is at
// or before it (0 if before the visible window). The engine contract keeps
// entity bar indices in full-frame coordinates, so the viewer positions regions
// by time to stay robust to the visible window.
function visibleIndexForTime(candles, isoTime) {
  if (!isoTime) return 0;
  const target = new Date(isoTime).getTime();
  let found = 0;
  candles.forEach((candle, index) => {
    if (new Date(candle.bar_close_time).getTime() <= target) found = index;
  });
  return found;
}

function ReplayChart({ replay, layers }) {
  const containerRef = useRef(null);
  const tooltipRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const markerApiRef = useRef(null);
  const auxiliarySeriesRef = useRef([]);

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#0f131a" },
        textColor: "#8892a0",
        fontFamily: "Inter, Segoe UI, sans-serif",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: { vertLines: { color: "#1d2430" }, horzLines: { color: "#1d2430" } },
      crosshair: {
        vertLine: { color: "#657184", labelBackgroundColor: "#2a3443" },
        horzLine: { color: "#657184", labelBackgroundColor: "#2a3443" },
      },
      rightPriceScale: { borderColor: "#252d39", scaleMargins: { top: 0.08, bottom: 0.12 } },
      timeScale: { borderColor: "#252d39", timeVisible: true, secondsVisible: false, rightOffset: 5, barSpacing: 8 },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#23b8aa", downColor: "#ff5d5d", borderVisible: false,
      wickUpColor: "#23b8aa", wickDownColor: "#ff5d5d",
      priceFormat: { type: "price", precision: 5, minMove: 0.00001 },
    });
    chartRef.current = chart;
    candleSeriesRef.current = candles;
    markerApiRef.current = createSeriesMarkers(candles, []);
    return () => chart.remove();
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    const candleSeries = candleSeriesRef.current;
    const markerApi = markerApiRef.current;
    if (!chart || !candleSeries || !markerApi) return undefined;
    auxiliarySeriesRef.current.forEach((series) => chart.removeSeries(series));
    auxiliarySeriesRef.current = [];
    const chartCandles = replay.candles.map((candle) => ({
      time: chartTime(candle.bar_close_time),
      open: candle.open, high: candle.high, low: candle.low, close: candle.close,
    }));
    candleSeries.setData(chartCandles);

    const markers = [];
    const latestLineByKind = Object.fromEntries(
      ["BOS", "CHOCH"].map((kind) => [kind, replay.structureEvents.filter((event) => event.kind === kind).at(-1)?.id]),
    );
    replay.structureEvents.forEach((event) => {
      const candle = replay.candles[event.confirmed_index];
      if (!candle) return;
      markers.push({
        time: chartTime(candle.bar_close_time),
        position: event.direction === "bearish" || event.swing_type === "HIGH" ? "aboveBar" : "belowBar",
        color: EVENT_COLORS[event.kind] || "#8793a4",
        shape: event.direction === "bearish" ? "arrowDown" : event.direction === "bullish" ? "arrowUp" : "circle",
        text: event.confirmed_index === replay.cursor
          ? (event.kind === "SWING" ? `SW ${event.swing_type}` : `${event.kind} ${event.direction}`)
          : "",
      });
      if (["BOS", "CHOCH"].includes(event.kind) && latestLineByKind[event.kind] === event.id && event.parent_id) {
        const parent = replay.structureEvents.find((candidate) => candidate.id === event.parent_id);
        const parentCandle = parent && replay.candles[parent.confirmed_index];
        if (parentCandle && Number.isFinite(Number(event.price))) {
          const line = chart.addSeries(LineSeries, {
            color: EVENT_COLORS[event.kind], lineWidth: 1, lineStyle: 2,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
          });
          line.setData([
            { time: chartTime(parentCandle.bar_close_time), value: Number(event.price) },
            { time: chartTime(replay.candle.bar_close_time), value: Number(event.price) },
          ]);
          auxiliarySeriesRef.current.push(line);
        }
      }
    });
    replay.wyckoffEvents.forEach((event) => {
      const candle = replay.candles[event.first_seen_index];
      if (!candle) return;
      markers.push({
        time: chartTime(candle.bar_close_time), position: "aboveBar",
        color: EVENT_COLORS[event.event_type] || "#c08cff", shape: "square",
        text: event.first_seen_index === replay.cursor ? event.event_type : "",
      });
    });
    replay.trades.forEach((trade) => {
      const entry = replay.candles[trade.entry_index];
      if (entry) markers.push({
        time: chartTime(entry.bar_close_time), position: trade.direction === "bullish" ? "belowBar" : "aboveBar",
        color: "#f6b94d", shape: trade.direction === "bullish" ? "arrowUp" : "arrowDown", text: "OBS",
      });
      const exit = trade.exit_index != null && replay.candles[trade.exit_index];
      if (exit) markers.push({
        time: chartTime(exit.bar_close_time), position: "aboveBar",
        color: trade.outcome === "TP" ? "#39ca8b" : "#ff5d5d", shape: "circle", text: trade.outcome,
      });
    });
    markerApi.setMarkers(markers.sort((a, b) => a.time - b.time));

    const range = replay.point.wyckoff?.range_ref || {};
    if (layers.RANGE && range.available) {
      [["high", "#c08cff"], ["mid", "#8793a4"], ["low", "#c08cff"]].forEach(([key, color]) => {
        if (!Number.isFinite(Number(range[key]))) return;
        const line = chart.addSeries(LineSeries, {
          color, lineWidth: 1, lineStyle: key === "mid" ? 2 : 0,
          crosshairMarkerVisible: false, lastValueVisible: key !== "mid", priceLineVisible: false,
        });
        line.setData([
          { time: chartCandles[0].time, value: Number(range[key]) },
          { time: chartCandles.at(-1).time, value: Number(range[key]) },
        ]);
        auxiliarySeriesRef.current.push(line);
      });
    }

    // Persistent Market State regions (FVG/OB/Breaker/BPR) with lifecycle.
    // The viewer only REPRESENTS the artifact; it does not compute rules.
    if (layers.MARKET && replay.marketState) {
      replay.marketState.entities.forEach((entity) => {
        if (!REGION_TYPES.has(entity.type)) return;
        if (!Number.isFinite(Number(entity.zone_high)) || !Number.isFinite(Number(entity.zone_low))) return;
        const startIndex = visibleIndexForTime(replay.candles, entity.tradable_time || entity.confirmation_time);
        const startTime = chartCandles[startIndex]?.time ?? chartCandles[0].time;
        const endTime = chartCandles.at(-1).time;
        const color = entity.state === "PARTIALLY_MITIGATED" ? "#f6b94d" : "#23b8aa";
        ["zone_high", "zone_low"].forEach((key) => {
          const line = chart.addSeries(LineSeries, {
            color, lineWidth: 1, lineStyle: 0,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
          });
          line.setData([
            { time: startTime, value: Number(entity[key]) },
            { time: endTime, value: Number(entity[key]) },
          ]);
          auxiliarySeriesRef.current.push(line);
        });
      });
    }

    const entityAtTime = new Map();
    replay.structureEvents.forEach((event) => {
      const candle = replay.candles[event.confirmed_index];
      if (candle) entityAtTime.set(chartTime(candle.bar_close_time), event);
    });
    replay.wyckoffEvents.forEach((event) => {
      const candle = replay.candles[event.first_seen_index];
      if (candle) entityAtTime.set(chartTime(candle.bar_close_time), event);
    });
    const onCrosshair = (param) => {
      const tooltip = tooltipRef.current;
      if (!tooltip || !param.time || !param.point) {
        if (tooltip) tooltip.hidden = true;
        return;
      }
      const entity = entityAtTime.get(Number(param.time));
      if (!entity) { tooltip.hidden = true; return; }
      tooltip.hidden = false;
      tooltip.style.left = `${Math.min(param.point.x + 16, containerRef.current.clientWidth - 275)}px`;
      tooltip.style.top = `${Math.max(8, param.point.y - 70)}px`;
      tooltip.textContent = [
        entity.id || entity.engine_event_id,
        entity.tf || entity.kind,
        entity.event_time || entity.confirmed_time,
        entity.price != null ? `price ${formatPrice(entity.price)}` : null,
        entity.parent_id ? `parent ${entity.parent_id}` : null,
        ...(entity.evidence_refs || []),
      ].filter(Boolean).join(" · ");
    };
    chart.subscribeCrosshairMove(onCrosshair);
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, chartCandles.length - 88), to: chartCandles.length + 4 });
    return () => chart.unsubscribeCrosshairMove(onCrosshair);
  }, [replay, layers]);

  return (
    <div className="chart-stage" data-visible-candles={replay.candles.length} data-cursor={replay.cursor}>
      <div className="chart-canvas" ref={containerRef} aria-label="Gráfico causal de velas cerradas" />
      <div className="chart-tooltip" ref={tooltipRef} hidden />
    </div>
  );
}

function LayerToggle({ label, code, active, count, onToggle }) {
  return (
    <button className={`layer-toggle ${active ? "is-active" : ""}`} type="button"
      aria-pressed={active} onClick={() => onToggle(code)}>
      <span className="toggle-dot" /><span>{label}</span><small>{count}</small>
    </button>
  );
}

function StatusCard({ label, value, tone, Icon }) {
  return (
    <div className={`status-card status-${tone}`}>
      <Icon size={17} weight="duotone" />
      <div><span>{label}</span><strong>{value}</strong></div>
    </div>
  );
}

function LoadingState({ error, onFile }) {
  return (
    <main className="load-shell">
      <div className="brand-mark"><ChartLine size={24} weight="bold" /></div>
      <span className="eyebrow">ICT Structure Lab</span>
      <h1>{error ? "No se pudo abrir el run" : "Cargando replay causal…"}</h1>
      <p>{error || "Validando visual_backtest.json v1.1 y sus políticas."}</p>
      {error && <label className="file-button"><FileArrowUp size={18} />Elegir JSON<input type="file" accept="application/json,.json" onChange={onFile} /></label>}
    </main>
  );
}

export function App() {
  const [artifact, setArtifact] = useState(null);
  const [error, setError] = useState("");
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [layers, setLayers] = useState(LAYER_DEFAULTS);

  const load = async (source) => {
    try {
      const data = typeof source?.text === "function"
        ? JSON.parse(await source.text())
        : await fetch("/run/visual_backtest.json", { cache: "no-store" }).then((response) => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
          });
      const validated = validateArtifact(data);
      setArtifact(validated);
      setCursor(0);
      setPlaying(true);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!playing || !artifact) return undefined;
    const timer = window.setInterval(() => {
      setCursor((current) => {
        if (current >= artifact.candles.length - 1) { setPlaying(false); return current; }
        return current + 1;
      });
    }, 700 / speed);
    return () => window.clearInterval(timer);
  }, [playing, speed, artifact]);
  useEffect(() => {
    const onKey = (event) => {
      if (!artifact || event.target.closest?.("button, input, select, textarea, summary")) return;
      if (event.key === "ArrowLeft") { setPlaying(false); setCursor((value) => Math.max(0, value - 1)); }
      if (event.key === "ArrowRight") { setPlaying(false); setCursor((value) => Math.min(artifact.candles.length - 1, value + 1)); }
      if (event.code === "Space") { event.preventDefault(); setPlaying((value) => !value); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [artifact]);

  const replay = useMemo(
    () => artifact ? visibleReplay(artifact, cursor, layers) : null,
    [artifact, cursor, layers],
  );
  if (!artifact || !replay) return <LoadingState error={error} onFile={(event) => load(event.target.files?.[0])} />;

  const snapshot = replay.point.wyckoff;
  const delta = replay.point.delta;
  const currentStructure = replay.structureEvents.filter((event) => event.confirmed_index === cursor);
  const currentWyckoff = replay.wyckoffEvents.filter((event) => event.first_seen_index === cursor);
  const phaseTone = PHASE_TONES[snapshot.phase] || "neutral";
  const counts = Object.fromEntries(
    ["SWING", "BOS", "CHOCH"].map((kind) => [kind, replay.structureEvents.filter((event) => event.kind === kind).length]),
  );
  const toggleLayer = (code) => setLayers((current) => ({ ...current, [code]: !current[code] }));
  const contextLayers = replay.point.ict?.context?.layers || {};
  const snapshotLayers = snapshot.layers || {};
  const lanes = ["D1", "H4", "H1", "M15", "M5", "M1"];
  const authorityManifest = artifact.data_manifest.timeframes[artifact.authority_tf];
  const scientific = artifact.scientific_status;
  const config = artifact.run_metadata.config;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block"><div className="brand-mark"><ChartLine size={20} weight="bold" /></div><div><strong>ICT Structure Lab</strong><span>Replay causal v1.1</span></div></div>
        <nav className="side-nav" aria-label="Secciones">
          <button className="nav-item is-selected" type="button" onClick={() => document.getElementById("replay")?.scrollIntoView()}><Eye size={18} />Reproductor</button>
          <button className="nav-item" type="button" onClick={() => document.getElementById("evidence")?.scrollIntoView()}><ShieldCheck size={18} />Evidencia</button>
        </nav>
        <details className="side-section" open>
          <summary className="section-label">Capas visibles</summary>
          <LayerToggle label="Swing" code="SWING" active={layers.SWING} count={counts.SWING} onToggle={toggleLayer} />
          <LayerToggle label="BOS" code="BOS" active={layers.BOS} count={counts.BOS} onToggle={toggleLayer} />
          <LayerToggle label="CHOCH" code="CHOCH" active={layers.CHOCH} count={counts.CHOCH} onToggle={toggleLayer} />
          <LayerToggle label="Wyckoff" code="WYCKOFF" active={layers.WYCKOFF} count={replay.wyckoffEvents.length} onToggle={toggleLayer} />
          <LayerToggle label="Rango" code="RANGE" active={layers.RANGE} count={snapshot.range_ref?.available ? 1 : 0} onToggle={toggleLayer} />
          <LayerToggle label="Market State" code="MARKET" active={layers.MARKET} count={replay.marketState?.entities?.length ?? 0} onToggle={toggleLayer} />
          <LayerToggle label="Setup State" code="SETUP" active={layers.SETUP} count={replay.setup?.estado ? 1 : 0} onToggle={toggleLayer} />
          <LayerToggle label="Operaciones" code="TRADES" active={layers.TRADES} count={replay.trades.length} onToggle={toggleLayer} />
        </details>
        <details className="side-section mtf-section" open>
          <summary className="section-label">Carriles multi-timeframe</summary>
          {lanes.map((tf) => {
            const layer = snapshotLayers[tf];
            const context = contextLayers[tf];
            const observational = ["M5", "M1"].includes(tf);
            return <div className={`mtf-lane ${artifact.authority_tf === tf ? "is-authority" : ""}`} key={tf}>
              <strong>{tf}</strong><span>{observational ? (replay.point.asof_by_tf[tf] ? "OBSERVACIONAL" : "NO DISPONIBLE") : (layer?.phase || context?.structure_bias || "NO DISPONIBLE")}</span>
              <small>{artifact.authority_tf === tf ? "AUTORIDAD" : observational ? (replay.point.asof_by_tf[tf] ? formatUtc(replay.point.asof_by_tf[tf]) : "—") : layer?.asof_time ? formatUtc(layer.asof_time) : "—"}</small>
            </div>;
          })}
        </details>
        <div className="provenance-card"><GitBranch size={16} /><div><span>Commit del run</span><code>{artifact.run_metadata.git_commit.slice(0, 12)}</code></div></div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="instrument-title"><div><strong>{artifact.symbol}</strong><span>{artifact.timeframe}</span></div><p>{formatUtc(replay.candle.bar_close_time)} UTC · vela visible {cursor + 1}</p></div>
          <div className="status-grid">
            <StatusCard label="Fase Wyckoff" value={snapshot.phase} tone={phaseTone} Icon={Clock} />
            <StatusCard label="Alineación ICT" value={snapshot.ict_alignment} tone={snapshot.conflict ? "red" : "green"} Icon={ShieldCheck} />
            <StatusCard label="Volumen" value={snapshot.volume_mode} tone="neutral" Icon={ChartLine} />
            <StatusCard label="FSM" value="RUNTIME BASIC" tone="amber" Icon={Flask} />
          </div>
          <label className="file-icon" title="Abrir otro visual_backtest.json"><FileArrowUp size={18} /><input type="file" accept="application/json,.json" aria-label="Abrir JSON de run" onChange={(event) => load(event.target.files?.[0])} /></label>
          <div className="read-only-badge">NO TRADING</div>
        </header>

        <div className="runtime-warning"><WarningCircle size={17} weight="fill" /><span><strong>Runtime diagnóstico causal.</strong> FSM básica, no WYCKOFF-7 · no edge · sin autorización de entrada o trading.</span></div>

        <div className="content-grid">
          <section className="chart-panel" id="replay">
            <div className="panel-heading"><div><span className="eyebrow">Replay vela cerrada</span><h1>{artifact.symbol} · {artifact.timeframe} · autoridad {artifact.authority_tf}</h1></div><div className="chart-legend"><span><i className="legend-swatch up" />Alcista</span><span><i className="legend-swatch down" />Bajista</span><span><i className="legend-line" />Estructura confirmada</span></div></div>
            <ReplayChart replay={replay} layers={layers} />
            <div className="replay-controls">
              <button className="icon-button" type="button" onClick={() => { setPlaying(false); setCursor(0); }} aria-label="Reiniciar"><ArrowCounterClockwise size={19} /></button>
              <button className="icon-button" type="button" onClick={() => { setPlaying(false); setCursor((value) => Math.max(0, value - 1)); }} aria-label="Vela anterior"><CaretLeft size={20} weight="bold" /></button>
              <button className="play-button" type="button" aria-pressed={playing} onClick={() => setPlaying((value) => !value)}>{playing ? <Pause size={20} weight="fill" /> : <Play size={20} weight="fill" />}{playing ? "Pausar" : "Reproducir"}</button>
              <button className="icon-button" type="button" onClick={() => { setPlaying(false); setCursor((value) => Math.min(artifact.candles.length - 1, value + 1)); }} aria-label="Siguiente vela"><CaretRight size={20} weight="bold" /></button>
              <div className="timeline-wrap"><input aria-label="Posición temporal" type="range" min="0" max={artifact.candles.length - 1} value={cursor} onInput={(event) => { setPlaying(false); setCursor(Number(event.target.value)); }} onChange={(event) => { setPlaying(false); setCursor(Number(event.target.value)); }} /><div className="timeline-labels"><span>Inicio {formatUtc(artifact.candles[0].bar_close_time)}</span><span>Ahora {formatUtc(replay.candle.bar_close_time)}</span></div></div>
              <label className="date-control"><span>Ir a cierre UTC</span><input type="datetime-local" aria-label="Seleccionar fecha y hora" min={toLocalInput(artifact.candles[0].bar_close_time)} max={toLocalInput(replay.candle.bar_close_time)} value={toLocalInput(replay.candle.bar_close_time)} onInput={(event) => { setPlaying(false); setCursor(cursorAtOrBefore(artifact.candles, event.target.value)); }} onChange={(event) => { setPlaying(false); setCursor(cursorAtOrBefore(artifact.candles, event.target.value)); }} /></label>
              <div className="speed-control" aria-label="Velocidad">{[1, 2, 4].map((value) => <button className={speed === value ? "is-selected" : ""} aria-pressed={speed === value} type="button" key={value} onClick={() => setSpeed(value)}>{value}×</button>)}</div>
            </div>
          </section>

          <aside className="inspector">
            <div className="inspector-header"><div><span className="eyebrow">Qué cambió en esta vela</span><h2>{delta.changed ? "Cambio observado" : "Sin cambio"}</h2></div><span className={`change-pill ${delta.changed ? "has-event" : ""}`}>{Object.keys(delta.fields || {}).length + (delta.new_wyckoff_event_ids || []).length} deltas</span></div>
            <div className="ohlc-grid">{[["Apertura", replay.candle.open], ["Máximo", replay.candle.high], ["Mínimo", replay.candle.low], ["Cierre", replay.candle.close]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{formatPrice(value)}</strong></div>)}</div>
            <div className="delta-card">{!delta.changed && <p>Sin cambio de fase, rango, alineación, conflicto, volumen ni evento.</p>}{Object.entries(delta.fields || {}).map(([field, change]) => <div className="delta-row" key={field}><strong>{field}</strong><span>{typeof change.from === "object" ? JSON.stringify(change.from) : String(change.from ?? "—")}</span><CaretRight size={12} /><span>{typeof change.to === "object" ? JSON.stringify(change.to) : String(change.to ?? "—")}</span></div>)}{(delta.new_wyckoff_event_ids || []).map((id) => <div className="delta-event" key={id}>Nuevo evento · {id}</div>)}</div>
            <div className={`phase-card phase-${phaseTone}`}><div className="phase-title"><Clock size={17} /><span>Snapshot Wyckoff real</span></div><strong>{snapshot.phase} · {snapshot.phase_state}</strong><p>{snapshot.explanation || "Sin explicación emitida."}</p><dl><div><dt>Rango alto</dt><dd>{formatPrice(snapshot.range_ref?.high)}</dd></div><div><dt>Rango medio</dt><dd>{formatPrice(snapshot.range_ref?.mid)}</dd></div><div><dt>Rango bajo</dt><dd>{formatPrice(snapshot.range_ref?.low)}</dd></div></dl></div>
            {layers.SETUP && replay.setup && (
              <div className={`setup-card ${replay.setup.estado === "SETUP_READY" ? "is-ready" : ""}`}>
                <div className="phase-title"><Flask size={17} /><span>Setup State · Context State / AHF</span></div>
                <strong>{replay.setup.estado} · {replay.setup.active_tf}</strong>
                <p>Proyección descriptiva del Context State canónico. No es señal de entrada.</p>
                <div className="setup-conditions">
                  <div><span>Presentes</span>{replay.setup.condiciones_presentes?.length ? replay.setup.condiciones_presentes.map((condition) => <code key={condition}>{condition}</code>) : <code>NINGUNA</code>}</div>
                  <div><span>Faltantes</span>{replay.setup.condiciones_faltantes?.length ? replay.setup.condiciones_faltantes.map((condition) => <code key={condition}>{condition}</code>) : <code>NINGUNA</code>}</div>
                </div>
                <div className="setup-policy"><span>policy</span><code>{replay.setup.policy}</code></div>
              </div>
            )}
            {layers.MARKET && replay.marketState && (
              <div className="market-card">
                <div className="phase-title"><GitBranch size={17} /><span>Market State persistente</span></div>
                <div className="market-delta">
                  <span>creadas</span><code>{replay.marketState.delta?.created?.length ?? 0}</code>
                  <span>transiciones</span><code>{replay.marketState.delta?.transitioned?.length ?? 0}</code>
                  <span>terminales</span><code>{replay.marketState.delta?.terminal?.length ?? 0}</code>
                </div>
                <div className="market-entities">
                  <div className="section-label">Entidades vivas ({replay.marketState.entities?.length ?? 0})</div>
                  {replay.marketState.entities?.length ? replay.marketState.entities.map((entity) => (
                    <article key={entity.id}>
                      <strong>{entity.type} · {entity.origin_tf}</strong>
                      <span>{entity.state} · {entity.role}</span>
                      <code>{entity.id}</code>
                    </article>
                  )) : <p>NINGUNA</p>}
                </div>
              </div>
            )}
            <div className="event-list"><div className="section-label">Entidades nuevas ahora</div>{[...currentStructure, ...currentWyckoff].length === 0 && <p>NINGUNA</p>}{[...currentStructure, ...currentWyckoff].map((event) => <article key={event.id}><strong>{event.id}</strong><span>{event.kind || event.event_type} · {event.tf || artifact.timeframe}</span><code>{event.parent_id || event.source_ref || "sin padre/ref"}</code></article>)}</div>
            <details className="evidence-panel" id="evidence" open><summary className="section-label">Evidencia exacta</summary><div className="evidence-line"><span>decision_time</span><code>{replay.point.decision_time}</code></div><div className="evidence-line"><span>barra</span><code>{replay.candle.bar_open_time} → {replay.candle.bar_close_time}</code></div>{Object.entries(replay.point.asof_by_tf).map(([tf, asof]) => <div className="evidence-line" key={tf}><span>asof {tf}</span><code>{asof || "NO DISPONIBLE"}</code></div>)}<div className="evidence-line"><span>volume source · {artifact.authority_tf}</span><code>{authorityManifest?.volume_source || "NO DISPONIBLE"}</code></div><div className="evidence-line"><span>run/config</span><code>{artifact.run_metadata.run_id} · {config.timeframes.join("/")} · warmup {config.warmup_bars} · {config.timestamp_semantics.toUpperCase()}_TIME</code></div><div className="evidence-line"><span>git lineage</span><code>{artifact.run_metadata.git_branch} · clean={String(artifact.run_metadata.generator_worktree_clean_before_run)} · py {artifact.run_metadata.python_version} · node {artifact.run_metadata.node_version}</code></div><div className="evidence-line"><span>config_sha256</span><code>{artifact.run_metadata.config_sha256}</code></div><div className="evidence-refs"><span>evidence_refs</span>{(snapshot.evidence_refs || []).length ? snapshot.evidence_refs.map((ref) => <code key={ref}>{ref}</code>) : <code>NINGUNA</code>}</div><div className="hash-line"><CheckCircle size={15} /><code>{artifact.run_metadata.artifact_content_sha256}</code></div></details>
            <div className="scientific-lock"><span>PIT Wyckoff</span><code>{scientific.pit_temporal_consistency.points_checked}/80 · {scientific.pit_temporal_consistency.status}</code><span>Factibilidad H1</span><code>{scientific.h1_feasibility.observations}/{scientific.h1_feasibility.required} · INSUFICIENTE</code><span>FSM</span><code>RUNTIME BASIC</code><span>Edge</span><code>NO PROBADO</code></div>
            <div className="trade-lock"><span>diagnostic_only</span><code>true</code><span>entry_authorized</span><code>false</code><span>can_trade</span><code>false</code><span>can_train</span><code>false</code><span>promotion_authorized</span><code>false</code></div>
          </aside>
        </div>
      </section>
    </main>
  );
}
