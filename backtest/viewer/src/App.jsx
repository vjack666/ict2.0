import { useEffect, useMemo, useState } from "react";
import { createAutoArtifact, validateArtifact, visibleReplay } from "./replayModel.js";
import { canonicalSnapshotCard } from "./canonicalSnapshotCard.js";
import "./styles.css";

function Lane({ tf, rows }) {
  const last = rows.at(-1);
  return <div className="lane"><strong>{tf}</strong><span>{rows.length} cierres</span><span>{last ? `${last.close.toFixed(5)} · ${last.observation_time}` : "sin barra"}</span></div>;
}

function Count({ label, value }) { return <div className="count"><b>{value}</b><span>{label}</span></div>; }

function CanonicalSnapshotPanel({ artifact, bridgeStatus, observedTime }) {
  const card = canonicalSnapshotCard(artifact, bridgeStatus, observedTime);
  return <section className={`canonical-panel ${card.state === "ABSTENCIÓN EXPLÍCITA" ? "abstaining" : ""}`} aria-label="Snapshot canónico de lectura">
    <div className="canonical-heading"><div><b>SNAPSHOT CANÓNICO · SOLO LECTURA</b><span>{card.reason}</span></div><span className="canonical-state">{card.state}</span></div>
    <div className="canonical-meta"><span>Bridge: {card.bridgeStatus}</span><span>Snapshot: {card.decisionTime ?? "NO DISPONIBLE"}</span><span>POLÍTICA REQUERIDA: CAN_TRADE=FALSE</span><span>DIAGNOSTIC_ONLY</span></div>
    {card.context && <div className="canonical-section"><b>Context State</b><span>{card.context.status} · {card.context.direction} · long: {String(card.context.allowLong)} · short: {String(card.context.allowShort)}</span></div>}
    {card.context && <div className="canonical-section"><b>Zonas canónicas</b><span>{card.zones.length ? card.zones.map((zone) => `${zone.id} · ${zone.tf} · ${zone.type} · ${zone.direction} · ${zone.state}${zone.low !== null && zone.high !== null ? ` · rango ${zone.low}–${zone.high}` : ""}`).join(" | ") : "SIN ZONAS PUBLICADAS"}</span></div>}
    {card.context && <div className="canonical-section"><b>BOS · Context State</b><span>{card.contextBos.length ? card.contextBos.map((item) => `${item.tf}: ${item.bos} · barra ${item.bar} · ${item.time ?? "sin hora"}`).join(" | ") : "SIN BOS PUBLICADO"}</span></div>}
    {card.context && <div className="canonical-section"><b>Microestructura M5/M1</b><span>{card.micro.map((item) => `${item.tf}: ${item.microBos} · ${item.trend}`).join(" | ")}</span></div>}
    {card.context && <div className="canonical-section"><b>Confirmación M5/M1</b><span>{card.confirmation.available ? `${card.confirmation.confirmed ? "CONFIRMADA" : "NO CONFIRMADA"} · M5: ${card.confirmation.detail.M5} · M1: ${card.confirmation.detail.M1}` : "NO PUBLICADA POR EL MOTOR"}</span></div>}
  </section>;
}

function Chart({ rows, zones, events = [], ghost, tf }) {
  const [zoom, setZoom] = useState(1); const [offset, setOffset] = useState(0); const [drag, setDrag] = useState(null);
  const visibleCount = Math.max(18, Math.min(180, Math.round(120 / zoom)));
  const end = Math.max(visibleCount, Math.min(rows.length, rows.length - offset)); const data = rows.slice(Math.max(0, end - visibleCount), end);
  if (!data.length) return <div className="chart empty-chart">Sin velas para este corte</div>;
  const lo = Math.min(...data.map((r) => Number(r.low))); const hi = Math.max(...data.map((r) => Number(r.high)));
  const pad = (hi - lo || 1) * .08; const min = lo - pad; const max = hi + pad;
  const chartWidth = 760; const rightMargin = 100; const x = (i) => 20 + i * (chartWidth / Math.max(1, data.length - 1)); const y = (v) => 250 - ((v - min) / (max - min)) * 220;
  const candle = (r, i, faded = false) => { const up = Number(r.close) >= Number(r.open); const color = up ? "#22c77a" : "#f05252"; return <g key={`${i}-${faded}`} opacity={faded ? .28 : 1}><line x1={x(i)} x2={x(i)} y1={y(r.high)} y2={y(r.low)} stroke="#aab8c7"/><rect x={x(i)-3.2} y={y(Math.max(r.open,r.close))} width="6.4" height={Math.max(2,y(Math.min(r.open,r.close))-y(Math.max(r.open,r.close)))} fill={color}/></g>; };
  const onWheel = (event) => { event.preventDefault(); setZoom((value) => Math.max(.6, Math.min(5, value * (event.deltaY < 0 ? 1.15 : .87)))); };
  const onPointerDown = (event) => { event.currentTarget.setPointerCapture(event.pointerId); setDrag(event.clientX); };
  const onPointerMove = (event) => { if (drag === null) return; const delta = event.clientX - drag; if (Math.abs(delta) > 8) { setOffset((value) => Math.max(0, Math.min(Math.max(0, rows.length - visibleCount), value + (delta < 0 ? 2 : -2)))); setDrag(event.clientX); } };
  const bos = events.filter((event) => event.tf === tf && event.kind === "BOS");
  return <div className="chart" onWheel={onWheel} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={() => setDrag(null)}><svg viewBox="0 0 900 280" role="img" aria-label="Gráfico de velas y zonas"><rect width="900" height="280" fill="#09121d"/>{(zones || []).map((z, i) => { const top = y(Math.max(Number(z.high ?? z.top), Number(z.low ?? z.bottom))); const bottom = y(Math.min(Number(z.high ?? z.top), Number(z.low ?? z.bottom))); return <rect key={z.id || i} x="20" y={top} width={chartWidth} height={Math.max(3,bottom-top)} fill={z.direction === "BEARISH" ? "#ef5350" : "#18c996"} opacity=".16" stroke={z.direction === "BEARISH" ? "#ef5350" : "#18c996"}/>; })}{data.map(candle)}{bos.map((event) => <g key={event.id}><line x1={x(Math.min(data.length-1, event.bar % Math.max(1,data.length)))} x2={x(Math.min(data.length-1, event.bar % Math.max(1,data.length)))} y1="20" y2="255" stroke="#f0c56a" strokeDasharray="3 5"/><text x={x(Math.min(data.length-1, event.bar % Math.max(1,data.length))) + 4} y="32" fill="#f0c56a" fontSize="11">BOS {event.direction === 1 ? "alcista" : "bajista"}</text></g>)}{ghost && [1,2,3,4].map((_, i) => candle({open:data.at(-1).close, close:data.at(-1).close + (i+1)*(max-min)*.025, high:data.at(-1).close + (i+1)*(max-min)*.04, low:data.at(-1).close - (max-min)*.01}, data.length+i, true))}<line x1={chartWidth + 20} x2={chartWidth + 20} y1="18" y2="258" stroke="#294252" strokeDasharray="4 6"/><text x="790" y="270" fill="#668294" fontSize="10">margen</text></svg>{ghost && <div className="ghost-label">SIMULACIÓN TEÓRICA · NO OBSERVADA · NO ES SEÑAL</div>}<div className="chart-help">Rueda: zoom · Arrastra: mover · {Math.round(zoom * 100)}%</div></div>;
}

export default function App() {
  const [artifact, setArtifact] = useState(() => createAutoArtifact({ days: 1 }));
  const [error, setError] = useState("");
  const [cursor, setCursor] = useState(0);
  const [tf, setTf] = useState("M15");
  const [ghost, setGhost] = useState(false);
  const [bridgeStatus, setBridgeStatus] = useState("LOCAL_AUTO_FIXTURE");
  useEffect(() => { let stopped = false; const refresh = async () => { try { const response = await fetch("http://127.0.0.1:8765/"); const live = await response.json(); if (stopped) return; setBridgeStatus(live.live_status ?? "BLOCKED"); if (live.live_status === "READY_MT5_CLOSED_ONLY") { setArtifact(live); setCursor(Math.max(0, live.timeline.length - 1)); setError(""); } else { setError(`Bridge MT5 no listo: ${live.error ?? live.live_status ?? "BLOCKED"}.`); } } catch { if (!stopped) { setBridgeStatus("UNAVAILABLE"); setError("MT5 no disponible: el snapshot canónico queda en abstención hasta reconexión."); } } }; refresh(); const id = setInterval(refresh, 5000); return () => { stopped = true; clearInterval(id); }; }, []);
  useEffect(() => { const id = setInterval(() => setCursor((value) => Math.min(value + 1, artifact.timeline.length - 1)), 60000); return () => clearInterval(id); }, [artifact.timeline.length]);
  const visible = useMemo(() => artifact ? visibleReplay(artifact, cursor) : null, [artifact, cursor]);

  async function openFile(event) {
    try {
      const parsed = JSON.parse(await event.target.files[0].text());
      const safe = validateArtifact(parsed);
      setArtifact(safe); setCursor(0); setError("");
    } catch (reason) { setError(String(reason.message ?? reason)); }
  }

  return <main>
    <header><div><p className="eyebrow">ICT SYSTEM · LOCAL_ONLY</p><h1>MTF Replay Orchestrator</h1></div><label className="upload">Abrir artefacto<input type="file" accept="application/json" onChange={openFile} /></label></header>
    {error && <p className="error">{error}</p>}
    {!visible ? <section className="empty"><h2>Visor causal 2.0</h2><p>Generando lectura automática…</p></section> : <>
      <section className="controls"><label>Temporalidad <select value={tf} onChange={(e) => setTf(e.target.value)}>{["H4","H1","M15","M5","M1"].map((value) => <option key={value}>{value}</option>)}</select></label><button onClick={() => setCursor(Math.max(0, cursor - 1))}>←</button><input aria-label="cursor" type="range" min="0" max={artifact.timeline.length - 1} value={cursor} onChange={(e) => setCursor(Number(e.target.value))}/><button onClick={() => setCursor(Math.min(artifact.timeline.length - 1, cursor + 1))}>→</button><code>{visible.time} · {new Date(visible.time).toISOString()}</code><span className="live-badge">{artifact.live_status || "LOCAL"}</span><button className={ghost ? "active" : ""} onClick={() => setGhost((value) => !value)}>Velas fantasma</button></section>
      <section className="chart-wrap"><h2>{artifact.symbol} · {tf} · mapa causal</h2><Chart rows={visible.candlesByTf[tf] || visible.candlesByTf[artifact.timeframe] || []} zones={visible.setups} events={artifact.structure_events || []} tf={tf} ghost={ghost}/>{ghost && <p className="explain">Escenario esperado: barrido de liquidez → desplazamiento → CHoCH/BOS → retorno a la zona. La confirmación real solo la emite el motor.</p>}</section>
      <CanonicalSnapshotPanel artifact={artifact} bridgeStatus={bridgeStatus} observedTime={visible.time}/>
      <section className="lanes">{Object.entries(visible.candlesByTf).sort().map(([tf, rows]) => <Lane key={tf} tf={tf} rows={rows}/>)}</section>
      <section className="counts"><Count label="Setups" value={visible.setups.length}/><Count label="Episodes" value={visible.episodes.length}/><Count label="Invalidaciones" value={visible.invalidations.length}/><Count label="Trades" value={visible.trades.length}/><Count label="Rechazos" value={visible.rejections.length}/></section>
      <section className="trace"><h2>Batch causal</h2><pre>{JSON.stringify(visible.tick, null, 2)}</pre></section>
    </>}
    <footer>DIAGNOSTIC_ONLY · CAN_TRADE=FALSE · El futuro permanece oculto hasta su cierre.</footer>
  </main>;
}
