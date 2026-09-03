import { useEffect, useMemo, useState } from "react";
import { createAutoArtifact, validateArtifact, visibleReplay } from "./replayModel.js";
import "./styles.css";

function Lane({ tf, rows }) {
  const last = rows.at(-1);
  return <div className="lane"><strong>{tf}</strong><span>{rows.length} cierres</span><span>{last ? `${last.close.toFixed(5)} · ${last.observation_time}` : "sin barra"}</span></div>;
}

function Count({ label, value }) { return <div className="count"><b>{value}</b><span>{label}</span></div>; }

function Chart({ rows, zones, ghost }) {
  const data = rows.slice(-120);
  if (!data.length) return <div className="chart empty-chart">Sin velas para este corte</div>;
  const lo = Math.min(...data.map((r) => Number(r.low))); const hi = Math.max(...data.map((r) => Number(r.high)));
  const pad = (hi - lo || 1) * .08; const min = lo - pad; const max = hi + pad;
  const x = (i) => 20 + i * (860 / Math.max(1, data.length - 1)); const y = (v) => 250 - ((v - min) / (max - min)) * 220;
  const candle = (r, i, faded = false) => { const up = Number(r.close) >= Number(r.open); const color = up ? "#22c77a" : "#f05252"; return <g key={`${i}-${faded}`} opacity={faded ? .28 : 1}><line x1={x(i)} x2={x(i)} y1={y(r.high)} y2={y(r.low)} stroke="#aab8c7"/><rect x={x(i)-3.2} y={y(Math.max(r.open,r.close))} width="6.4" height={Math.max(2,y(Math.min(r.open,r.close))-y(Math.max(r.open,r.close)))} fill={color}/></g>; };
  return <div className="chart"><svg viewBox="0 0 900 280" role="img" aria-label="Gráfico de velas y zonas"><rect width="900" height="280" fill="#09121d"/>{(zones || []).map((z, i) => { const top = y(Math.max(Number(z.high ?? z.top), Number(z.low ?? z.bottom))); const bottom = y(Math.min(Number(z.high ?? z.top), Number(z.low ?? z.bottom))); return <rect key={z.id || i} x="20" y={top} width="860" height={Math.max(3,bottom-top)} fill={z.direction === "BEARISH" ? "#ef5350" : "#18c996"} opacity=".16" stroke={z.direction === "BEARISH" ? "#ef5350" : "#18c996"}/>; })}{data.map(candle)}{ghost && [1,2,3,4].map((_, i) => candle({open:data.at(-1).close, close:data.at(-1).close + (i+1)*(max-min)*.025, high:data.at(-1).close + (i+1)*(max-min)*.04, low:data.at(-1).close - (max-min)*.01}, data.length+i, true))}</svg>{ghost && <div className="ghost-label">SIMULACIÓN TEÓRICA · NO OBSERVADA · NO ES SEÑAL</div>}</div>;
}

export default function App() {
  const [artifact, setArtifact] = useState(() => createAutoArtifact({ days: 1 }));
  const [error, setError] = useState("");
  const [cursor, setCursor] = useState(0);
  const [tf, setTf] = useState("M15");
  const [ghost, setGhost] = useState(false);
  useEffect(() => { let stopped = false; const refresh = async () => { try { const response = await fetch("http://127.0.0.1:8765/"); const live = await response.json(); if (!stopped && live.live_status === "READY_MT5_CLOSED_ONLY") { setArtifact(live); setCursor(Math.max(0, live.timeline.length - 1)); setError(""); } } catch { if (!stopped) setError("MT5 no disponible: mostrando lectura local hasta reconexión."); } }; refresh(); const id = setInterval(refresh, 5000); return () => { stopped = true; clearInterval(id); }; }, []);
  useEffect(() => { const id = setInterval(() => setCursor((value) => Math.min(value + 1, artifact.timeline.length - 1)), 5000); return () => clearInterval(id); }, [artifact.timeline.length]);
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
      <section className="controls"><label>Temporalidad <select value={tf} onChange={(e) => setTf(e.target.value)}>{["H4","H1","M15","M5"].map((value) => <option key={value}>{value}</option>)}</select></label><button onClick={() => setCursor(Math.max(0, cursor - 1))}>←</button><input aria-label="cursor" type="range" min="0" max={artifact.timeline.length - 1} value={cursor} onChange={(e) => setCursor(Number(e.target.value))}/><button onClick={() => setCursor(Math.min(artifact.timeline.length - 1, cursor + 1))}>→</button><code>{visible.time} · {new Date(visible.time).toISOString()}</code><span className="live-badge">{artifact.live_status || "LOCAL"}</span><button className={ghost ? "active" : ""} onClick={() => setGhost((value) => !value)}>Velas fantasma</button></section>
      <section className="chart-wrap"><h2>{artifact.symbol} · {tf} · mapa causal</h2><Chart rows={visible.candlesByTf[tf] || visible.candlesByTf[artifact.timeframe] || []} zones={visible.setups} ghost={ghost}/>{ghost && <p className="explain">Escenario esperado: barrido de liquidez → desplazamiento → CHoCH/BOS → retorno a la zona. La confirmación real solo la emite el motor.</p>}</section>
      <section className="lanes">{Object.entries(visible.candlesByTf).sort().map(([tf, rows]) => <Lane key={tf} tf={tf} rows={rows}/>)}</section>
      <section className="counts"><Count label="Setups" value={visible.setups.length}/><Count label="Episodes" value={visible.episodes.length}/><Count label="Invalidaciones" value={visible.invalidations.length}/><Count label="Trades" value={visible.trades.length}/><Count label="Rechazos" value={visible.rejections.length}/></section>
      <section className="trace"><h2>Batch causal</h2><pre>{JSON.stringify(visible.tick, null, 2)}</pre></section>
    </>}
    <footer>DIAGNOSTIC_ONLY · CAN_TRADE=FALSE · El futuro permanece oculto hasta su cierre.</footer>
  </main>;
}
