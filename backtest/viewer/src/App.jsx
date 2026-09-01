import { useMemo, useState } from "react";
import { validateArtifact, visibleReplay } from "./replayModel.js";
import "./styles.css";

function Lane({ tf, rows }) {
  const last = rows.at(-1);
  return <div className="lane"><strong>{tf}</strong><span>{rows.length} cierres</span><span>{last ? `${last.close.toFixed(5)} · ${last.observation_time}` : "sin barra"}</span></div>;
}

function Count({ label, value }) { return <div className="count"><b>{value}</b><span>{label}</span></div>; }

export default function App() {
  const [artifact, setArtifact] = useState(null);
  const [error, setError] = useState("");
  const [cursor, setCursor] = useState(0);
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
    {!visible ? <section className="empty"><h2>Visor causal 2.0</h2><p>Carga un artefacto MTF_REPLAY. Esta interfaz observa; no calcula señales ni autoriza trading.</p></section> : <>
      <section className="controls"><button onClick={() => setCursor(Math.max(0, cursor - 1))}>←</button><input aria-label="cursor" type="range" min="0" max={artifact.timeline.length - 1} value={cursor} onChange={(e) => setCursor(Number(e.target.value))}/><button onClick={() => setCursor(Math.min(artifact.timeline.length - 1, cursor + 1))}>→</button><code>{visible.time}</code></section>
      <section className="lanes">{Object.entries(visible.candlesByTf).sort().map(([tf, rows]) => <Lane key={tf} tf={tf} rows={rows}/>)}</section>
      <section className="counts"><Count label="Setups" value={visible.setups.length}/><Count label="Episodes" value={visible.episodes.length}/><Count label="Invalidaciones" value={visible.invalidations.length}/><Count label="Trades" value={visible.trades.length}/><Count label="Rechazos" value={visible.rejections.length}/></section>
      <section className="trace"><h2>Batch causal</h2><pre>{JSON.stringify(visible.tick, null, 2)}</pre></section>
    </>}
    <footer>DIAGNOSTIC_ONLY · CAN_TRADE=FALSE · El futuro permanece oculto hasta su cierre.</footer>
  </main>;
}
