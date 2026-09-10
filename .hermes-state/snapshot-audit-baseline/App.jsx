import { Journal } from "./Journal.jsx";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  RefreshCw,
  Shield,
  Square,
  Play,
  Maximize2,
} from "lucide-react";
import {
  CandlestickSeries,
  HistogramSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
} from "lightweight-charts";
const TFS = ["D1", "H4", "H1", "M15", "M5", "M1"],
  TABS = ["Mercado", "ICT / Wyckoff", "Bot mecánico", "Posiciones", "Bitácora"];
const EMPTY = {
  connection: { status: "WAITING" },
  engine: { status: "WAITING" },
  bot: { state: "OFF" },
  candles_by_tf: {},
  open_candles_by_tf: {},
  events: [],
  positions: [],
};
const num = (v, d = 5) =>
  v == null || !Number.isFinite(Number(v)) ? "—" : Number(v).toFixed(d);
const text = (v) =>
  v == null
    ? "—"
    : typeof v === "boolean"
      ? v
        ? "Sí"
        : "No"
      : typeof v === "object"
        ? JSON.stringify(v)
        : String(v);
const stamp = (v) =>
  !v
    ? "Sin dato"
    : new Date(typeof v === "number" ? v * 1000 : v).toLocaleString("es-EC", {
        timeZone: "America/Guayaquil",
        hour12: false,
      });
const direction = (v) =>
  ["BULLISH", "BUY", "LONG", 1, "1"].includes(v)
    ? "Alcista"
    : ["BEARISH", "SELL", "SHORT", -1, "-1"].includes(v)
      ? "Bajista"
      : v === "MIXED"
        ? "Mixta / rango"
        : "Sin dirección";
function Badge({ children, tone = "" }) {
  return <span className={"badge " + tone}>{children}</span>;
}
function Row({ label, value }) {
  return (
    <div className="row">
      <span>{label}</span>
      <strong>{text(value)}</strong>
    </div>
  );
}
function Empty({ children }) {
  return (
    <div className="empty">
      <AlertTriangle size={17} />
      <span>{children}</span>
    </div>
  );
}
const READINESS_LABELS = {
  execution_enabled: "Ejecución habilitada",
  snapshot: "Snapshot válido y vigente",
  direction: "Dirección operable",
  probability: "Probabilidad ≥ 70 %",
  m15_confirmation: "Confirmación M15",
  session: "Sesión de entrada",
};
function ReadinessPanel({ readiness }) {
  const gates = readiness?.gates ?? [];
  const ready = readiness?.ready === true;
  return (
    <section
      className={`readiness-panel ${ready ? "is-ready" : "is-blocked"}`}
      aria-label="Readiness de entrada automática"
    >
      <div className="readiness-head">
        <div>
          <small>READINESS · ENTRADA AUTOMÁTICA</small>
          <h3>
            {ready
              ? "Todos los requisitos cumplen"
              : "Entrada bloqueada de forma segura"}
          </h3>
        </div>
        <Badge tone={ready ? "good" : "warn"}>
          {ready ? "LISTO" : "NO LISTO"}
        </Badge>
      </div>
      {!gates.length ? (
        <div className="readiness-gate failed">
          <span className="gate-mark" aria-hidden="true">×</span>
          <div>
            <strong>Readiness no disponible</strong>
            <p>
              El servicio todavía no publicó la evaluación. La entrada
              permanece bloqueada.
            </p>
          </div>
        </div>
      ) : (
        gates.map((gate) => (
          <div
            className={`readiness-gate ${gate.passed ? "passed" : "failed"}`}
            key={gate.id}
          >
            <span className="gate-mark" aria-hidden="true">
              {gate.passed ? "✓" : "×"}
            </span>
            <div>
              <strong>
                {READINESS_LABELS[gate.id] ?? gate.label ?? gate.id}
              </strong>
              <p>{gate.detail ?? gate.code}</p>
            </div>
            <Badge tone={gate.passed ? "good" : "warn"}>
              {gate.passed ? "CUMPLE" : "FALLA"}
            </Badge>
          </div>
        ))
      )}
      <p className="readiness-footnote">
        Este panel explica la posibilidad de una entrada; armar solo inicia el
        loop. Los gates se vuelven a validar antes de cualquier orden.
      </p>
    </section>
  );
}
function useFeed() {
  const [state, setState] = useState(EMPTY),
    [error, setError] = useState(""),
    busy = useRef(false),
    abort = useRef(),
    versions = useRef({});
  const refresh = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    const c = new AbortController();
    abort.current = c;
    const timeout = setTimeout(() => c.abort(), 4500);
    try {
      const r = await fetch(
        "/api/state?" + new URLSearchParams(versions.current),
        { signal: c.signal },
      );
      if (!r.ok) throw Error("Bridge HTTP " + r.status);
      const n = await r.json();
      versions.current = {
        bars_version: n.bars_version,
        engine_version: n.engine_version,
      };
      setState((o) => ({
        ...o,
        ...n,
        candles_by_tf: n.candles_by_tf ?? o.candles_by_tf,
        engine: {
          ...n.engine,
          snapshot:
            n.engine?.snapshot === undefined
              ? o.engine?.snapshot
              : n.engine.snapshot,
        },
      }));
      setError("");
    } catch (e) {
      setError(e.name === "AbortError" ? "El bridge no responde" : e.message);
    } finally {
      clearTimeout(timeout);
      busy.current = false;
    }
  }, []);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 1000);
    return () => {
      clearInterval(t);
      abort.current?.abort();
    };
  }, [refresh]);
  return { state, error, refresh };
}
// Only projects canonical geometry onto the chart; never detects market events.
class ZonePrimitive {
  constructor(zones) {
    this.zones = zones;
    this.view = {
      zOrder: () => "bottom",
      renderer: () => ({
        draw: (target) =>
          target.useBitmapCoordinateSpace((s) => {
            const c = s.context;
            for (const z of this.zones) {
              const a = this.series?.priceToCoordinate(
                  Number(z.zone_high ?? z.high),
                ),
                b = this.series?.priceToCoordinate(Number(z.zone_low ?? z.low));
              if (a == null || b == null) continue;
              const t = Date.parse(z.tradable_time ?? z.creation_time) / 1000,
                x = Number.isFinite(t)
                  ? this.chart.timeScale().timeToCoordinate(t)
                  : null;
              c.fillStyle = "rgba(61,170,156,.12)";
              c.fillRect(
                (x ?? 0) * s.horizontalPixelRatio,
                a * s.verticalPixelRatio,
                s.bitmapSize.width - (x ?? 0) * s.horizontalPixelRatio,
                (b - a) * s.verticalPixelRatio,
              );
              c.fillStyle = "#80b9b1";
              c.font = `${10 * s.verticalPixelRatio}px system-ui`;
              c.fillText(
                `${z.type ?? "FVG"} · ${z.authority_tf ?? ""} · ${z.state ?? ""}`,
                Math.max(10, (x ?? 0) + 8) * s.horizontalPixelRatio,
                (a + 13) * s.verticalPixelRatio,
              );
            }
          }),
      }),
    };
  }
  attached({ chart, series, requestUpdate }) {
    this.chart = chart;
    this.series = series;
    requestUpdate();
  }
  paneViews() {
    return [this.view];
  }
  updateAllViews() {}
}
function Chart({ state, tf, zones }) {
  const root = useRef(),
    chart = useRef(),
    candles = useRef(),
    volume = useRef(),
    key = useRef(""),
    lastTf = useRef("");
  const bars = state.candles_by_tf?.[tf] ?? [],
    open = state.open_candles_by_tf?.[tf];
  useEffect(() => {
    chart.current = createChart(root.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#09121d" },
        textColor: "#8ea2b4",
        fontFamily: "Segoe UI, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#13212c" },
        horzLines: { color: "#13212c" },
      },
      timeScale: { timeVisible: true, borderColor: "#233645", rightOffset: 5 },
      rightPriceScale: { borderColor: "#233645" },
      crosshair: { mode: 0 },
    });
    candles.current = chart.current.addSeries(CandlestickSeries, {
      upColor: "#47c7b4",
      downColor: "#ea6873",
      borderVisible: false,
      wickUpColor: "#47c7b4",
      wickDownColor: "#ea6873",
      priceFormat: { type: "price", precision: 5, minMove: 0.00001 },
    });
    candles.current
      .priceScale()
      .applyOptions({ scaleMargins: { top: 0.08, bottom: 0.2 } });
    volume.current = chart.current.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    volume.current
      .priceScale()
      .applyOptions({ scaleMargins: { top: 0.86, bottom: 0 } });
    return () => {
      const old = chart.current;
      candles.current = null;
      volume.current = null;
      chart.current = null;
      old.remove();
    };
  }, []);
  useEffect(() => {
    const k = `${tf}:${state.bars_version}`;
    if (!candles.current || key.current === k) return;
    candles.current.setData(bars);
    volume.current.setData(
      bars.map((b) => ({
        time: b.time,
        value: b.tick_volume,
        color: b.close >= b.open ? "#21483f" : "#4a3038",
      })),
    );
    if (tf !== lastTf.current && bars.length)
      chart.current.timeScale().setVisibleLogicalRange({
        from: Math.max(0, bars.length - 140),
        to: bars.length + 5,
      });
    key.current = k;
    lastTf.current = tf;
  }, [bars, tf, state.bars_version]);
  useEffect(() => {
    if (open && candles.current) {
      candles.current.update(open);
      volume.current.update({
        time: open.time,
        value: open.tick_volume,
        color: "#354750",
      });
    }
  }, [open, tf]);
  useEffect(() => {
    if (!candles.current) return;
    const p = new ZonePrimitive(zones.slice(-4));
    candles.current.attachPrimitive(p);
    return () => candles.current?.detachPrimitive(p);
  }, [zones, tf]);
  useEffect(() => {
    if (!candles.current) return;
    const layer = state.engine.snapshot?.context_state?.layers?.[tf];
    const asof = layer ? Date.parse(layer.asof_time) / 1000 : NaN;
    const last = bars.findIndex((b) => b.time === asof);
    const index = last >= 0 ? last - (layer.asof_bar - layer.last_bos_bar) : -1;
    const row = layer?.last_bos_bar != null && index >= 0 ? bars[index] : null;
    const markers = createSeriesMarkers(
      candles.current,
      row
        ? [
            {
              time: row.time,
              position:
                layer.last_bos_direction === 1 ? "belowBar" : "aboveBar",
              color: "#e2d4b4",
              shape: "circle",
              text: "BOS " + tf,
            },
          ]
        : [],
    );
    return () => {
      if (candles.current) markers.detach();
    };
  }, [state.engine_version, tf, bars]);
  return (
    <div
      className="chart"
      ref={root}
      aria-label={"Gráfico interactivo " + tf}
    />
  );
}
function Context({ snapshot: s, engine }) {
  const layers = s?.context_state?.layers ?? {};
  return (
    <section className="panel context">
      <div className="section-label">
        CONTEXTO ICT / WYCKOFF{" "}
        <Badge tone={engine.status === "READY" ? "good" : "warn"}>
          {engine.status}
        </Badge>
      </div>
      {engine.status !== "READY" && (
        <p className="notice">
          {engine.status === "RUNNING"
            ? "Actualizando análisis; lectura anterior visible."
            : "Lectura no vigente; esperar datos frescos."}
        </p>
      )}
      {s ? (
        <>
          <div className="context-item">
            <small>CONTEXTO SUPERIOR</small>
            <h2 className="teal">
              {direction(s.context_state?.constraints?.direction_hint)}
            </h2>
            <p>D1 → H4 → H1 → M15</p>
          </div>
          {["H4", "M15"].map((tf) => (
            <div className="context-item" key={tf}>
              <small>{tf}</small>
              <h3>
                {direction(
                  layers[tf]?.structure_bias ??
                    layers[tf]?.trend ??
                    layers[tf]?.last_bos_direction,
                )}
              </h3>
              <Row label="Régimen" value={layers[tf]?.regime} />
              <Row
                label="BOS"
                value={direction(layers[tf]?.last_bos_direction)}
              />
            </div>
          ))}
          <div className="context-item">
            <small>M5 / M1</small>
            <h3 className="amber">
              {s.micro_confirmation?.confirmed
                ? "Confirmación publicada"
                : "Esperando confirmación"}
            </h3>
            <Row label="M5" value={s.micro_confirmation?.detail?.M5} />
            <Row label="M1" value={s.micro_confirmation?.detail?.M1} />
            <p>Confirmación descriptiva del motor.</p>
          </div>
        </>
      ) : (
        <Empty>Esperando el primer análisis canónico.</Empty>
      )}
      {engine.error && <p className="notice">{engine.error}</p>}
    </section>
  );
}
function Wyckoff({ snapshot }) {
  const w = snapshot?.wyckoff;
  return (
    <section className="panel">
      <div className="section-label">WYCKOFF · DIAGNÓSTICO</div>
      {w ? (
        <>
          <h3 className="teal">{text(w.phase)}</h3>
          <Row label="Autoridad" value={w.authority_tf} />
          <Row label="Alineación ICT" value={w.ict_alignment} />
          <Row label="Conflicto" value={w.conflict} />
          <Row label="Volumen" value={w.volume_mode} />
          <p className="subtle">{w.explanation}</p>
        </>
      ) : (
        <Empty>Sin evidencia Wyckoff publicada.</Empty>
      )}
    </section>
  );
}
function Instruments({ state }) {
  return (
    <aside className="left-rail">
      <section className="panel instruments">
        <div className="section-label">INSTRUMENTOS</div>
        <div className="watch-head">
          <span>Símbolo</span>
          <span>Bid</span>
          <span>Ask</span>
        </div>
        <div className="watch-row">
          <strong>EURUSD</strong>
          <span className="teal">{num(state.tick?.bid)}</span>
          <span>{num(state.tick?.ask)}</span>
        </div>
        <div className="instrument-meta">
          Euro / Dólar estadounidense
          <br />
          Feed del terminal seleccionado
        </div>
        <div className="section-label muted">TEMPORALIDADES DISPONIBLES</div>
        {TFS.map((tf) => (
          <Row
            key={tf}
            label={tf}
            value={
              state.candles_by_tf?.[tf]?.length
                ? `${state.candles_by_tf[tf].length} velas`
                : "Esperando"
            }
          />
        ))}
      </section>
      <section className="panel">
        <div className="section-label">CONEXIÓN</div>
        <Row label="Estado" value={state.connection.status} />
        <Row label="Servidor" value={state.account?.server} />
        <Row label="Plataforma" value="MetaTrader 5" />
        <Row
          label="Antigüedad tick"
          value={state.tick ? `${state.tick.age_seconds} s` : "—"}
        />
        <Row
          label="Reloj terminal"
          value={`UTC+${state.connection.server_utc_offset_hours ?? "?"}`}
        />
        <Row label="Gráfico" value="UTC" />
        <Row label="Cuenta" value={state.account?.login} />
        <Row label="Entorno" value={state.account?.environment} />
      </section>
    </aside>
  );
}
function Events({ state, compact = false }) {
  return (
    <section className="panel events">
      <div className="section-label">
        {compact ? "ACTIVIDAD RECIENTE" : "BITÁCORA DE LA SESIÓN"}
        <span>{state.events.length} eventos</span>
      </div>
      {state.events.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Hora Guayaquil</th>
                <th>Evento</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {state.events.slice(0, compact ? 5 : 100).map((e, i) => (
                <tr key={i}>
                  <td>{stamp(e.time)}</td>
                  <td>{e.event}</td>
                  <td>{text(e.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty>Los eventos aparecerán al recibir el primer análisis.</Empty>
      )}
    </section>
  );
}
function Market({ state, tf, setTf, onAction, onBot }) {
  const s = state.engine.snapshot,
    zones = useMemo(
      () =>
        (s?.object_projection ?? s?.canonical_zones?.[tf] ?? []).filter(
          (z) =>
            (z.authority_tf ?? tf) === tf &&
            ["ACTIVE", "PARTIALLY_MITIGATED"].includes(z.state) &&
            Number.isFinite(Number(z.zone_high ?? z.high)) &&
            Number.isFinite(Number(z.zone_low ?? z.low)),
        ),
      [s, tf],
    );
  return (
    <div className="market-grid">
      <Instruments state={state} />
      <div className="center">
        <section className="chart-panel panel">
          <div className="chart-toolbar">
            <strong>EURUSD</strong>
            <div className="timeframes">
              {TFS.map((t) => (
                <button
                  key={t}
                  onClick={() => setTf(t)}
                  className={t === tf ? "selected" : ""}
                >
                  {t}
                </button>
              ))}
            </div>
            <button
              className="icon-button"
              aria-label="Ampliar gráfico"
              onClick={(e) =>
                e.currentTarget.closest(".chart-panel").requestFullscreen?.()
              }
            >
              <Maximize2 size={16} />
            </button>
          </div>
          <div className="quote-line">
            <span>Euro / Dólar estadounidense · {tf}</span>
            <span className="teal">{num(state.tick?.bid)}</span>
            <small>Spread {num(state.tick?.spread_points, 1)} puntos</small>
          </div>
          <Chart state={state} tf={tf} zones={zones} />
          <div className="chart-caption">
            <span>Vela actual en formación · análisis solo con cerradas</span>
            <span>Zoom / arrastrar · UTC</span>
          </div>
        </section>
        <Events state={state} compact />
      </div>
      <aside className="right-rail">
        <Context snapshot={s} engine={state.engine} />
        <Wyckoff snapshot={s} />
        <section className="panel">
          <div className="section-label">ANÁLISIS RÁPIDO</div>
          <button className="primary wide" onClick={() => onAction("analyze")}>
            <Activity size={18} />
            Analizar
          </button>
          <p className="subtle">
            {state.engine.duration_ms
              ? `${num(state.engine.duration_ms / 1000, 1)} s último cálculo`
              : "Primer cálculo en curso"}{" "}
            · proceso separado
          </p>
        </section>
        <section className="panel">
          <div className="section-label">
            BOT MECÁNICO <Badge>{state.bot.state}</Badge>
          </div>
          <Row
            label="Ejecución"
            value={state.bot.execution_enabled ? "Habilitada" : "Deshabilitada"}
          />
          <button className="link-button" onClick={onBot}>
            Abrir controles del bot →
          </button>
        </section>
      </aside>
    </div>
  );
}
function Evidence({ state }) {
  const s = state.engine.snapshot;
  if (!s) return <Empty>Esperando el primer snapshot del motor.</Empty>;
  return (
    <div className="detail-grid">
      <Context snapshot={s} engine={state.engine} />
      <Wyckoff snapshot={s} />
      <section className="panel">
        <div className="section-label">TRAZABILIDAD</div>
        <Row label="Estado" value={s.status} />
        <Row label="Decisión UTC" value={stamp(s.decision_time)} />
        <Row label="Commit" value={s.generator_commit?.slice(0, 12)} />
        <Row label="Política" value={s.policy} />
        <Row label="Autorización de orden" value={s.entry_authorized} />
        <Row label="Origen" value={s.transport?.kind} />
        <p className="subtle">
          Hashes de las velas cerradas en memoria; no equivalen a certificación
          histórica.
        </p>
      </section>
      <section className="panel full">
        <div className="section-label">ZONAS CANÓNICAS</div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>TF</th>
                <th>Tipo</th>
                <th>Dirección</th>
                <th>Zona</th>
                <th>Estado</th>
                <th>ID</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(s.canonical_zones ?? {}).flatMap(([tf, rows]) =>
                rows.map((z) => (
                  <tr key={z.id}>
                    <td>{tf}</td>
                    <td>{z.type}</td>
                    <td>{direction(z.direction)}</td>
                    <td>
                      {num(z.zone_low ?? z.low)} — {num(z.zone_high ?? z.high)}
                    </td>
                    <td>{z.state ?? z.status}</td>
                    <td className="id-cell">{z.id}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel full">
        <div className="section-label">EXPLORADOR DEL MOTOR</div>
        {[
          "daily_motor",
          "context_state",
          "micro_structure",
          "micro_confirmation",
          "sequence",
          "wyckoff",
          "object_projection",
          "relations",
          "lineage_refs",
          "source_hashes",
        ].map((k) => (
          <details key={k}>
            <summary>{k.replaceAll("_", " ")}</summary>
            <pre>{JSON.stringify(s[k] ?? null, null, 2)}</pre>
          </details>
        ))}
      </section>
    </div>
  );
}
function BotControl({ state, onAction, onEmergencyDisarm, pending }) {
  const [confirm, setConfirm] = useState(""),
    b = state.bot,
    a = state.account ?? {},
    cycle = b.cycle;
  return (
    <div className="detail-grid">
      <section className="panel bot-main">
        <div className="section-label">
          BOT MECÁNICO <Badge>{b.state}</Badge>
        </div>
        <h1>Control de ejecución</h1>
        <Row
          label="Modo de prueba"
          value={b.demo_wait_enabled ? "DEMO · cuenta fijada" : "Manual"}
        />
        <details open>
          <summary>Sesiones · hora de Guayaquil</summary>
          <p className="subtle">
            Lunes a viernes · cambios estacionales automáticos
          </p>
          {(b.session_schedule?.sessions ?? []).map((w) => (
            <div className="context-item" key={w.name}>
              <Row label={w.name} value={w.active ? "ABIERTA" : "En espera"} />
              <Row label="Inicio Guayaquil" value={stamp(w.start_guayaquil)} />
              <Row label="Fin Guayaquil" value={stamp(w.end_guayaquil)} />
            </div>
          ))}
        </details>
        <details>
          <summary>Caja negra · decisiones y envíos</summary>
          <p className="subtle">{b.black_box?.path ?? "Iniciando registro"}</p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Guayaquil</th>
                  <th>Evento</th>
                  <th>Motivo / resultado</th>
                </tr>
              </thead>
              <tbody>
                {(b.black_box?.tail ?? [])
                  .slice()
                  .reverse()
                  .map((e, i) => (
                    <tr key={i}>
                      <td>{stamp(e.time)}</td>
                      <td>{e.event}</td>
                      <td>{text(e.reason ?? e.error ?? e.outcome)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <p className="subtle">
            El archivo conserva el detalle de las decisiones, peticiones y
            respuestas.
          </p>
        </details>
        <p className="subtle">
          El ejecutor consume su snapshot operativo y confirma con estocástico
          M15. La lectura ICT/Wyckoff se presenta por separado.
        </p>
        <ReadinessPanel readiness={b.readiness} />
        <div className="action-row">
          <button
            className="primary"
            disabled={pending}
            onClick={() => onAction("analyze")}
          >
            <RefreshCw size={16} />
            Analizar
          </button>
          <button
            disabled={!b.execution_enabled || pending}
            onClick={() => setConfirm("arm")}
          >
            <Play size={16} />
            Armar bot · iniciar loop
          </button>
          <button
            disabled={!b.execution_enabled || pending || b.state === "OFF"}
            onClick={() => setConfirm("manual-buy")}
          >
            Compra manual
          </button>
          <button
            disabled={!b.execution_enabled || pending || b.state === "OFF"}
            onClick={() => setConfirm("manual-sell")}
          >
            Venta manual
          </button>
          <button
            className="danger"
            title="Detener nuevas entradas inmediatamente"
            onClick={onEmergencyDisarm}
          >
            <Square size={16} />
            Apagar
          </button>
          <button
            className="danger"
            disabled={!cycle || !b.execution_enabled || pending}
            onClick={() => setConfirm("close-cycle")}
          >
            Cerrar ciclo
          </button>
        </div>
        {confirm && (
          <div className="confirmation">
            <h3>
              {confirm === "arm"
                ? "Confirmar activación"
                : confirm === "manual-buy"
                  ? "Confirmar compra manual"
                  : confirm === "manual-sell"
                    ? "Confirmar venta manual"
                    : "Confirmar cierre de posiciones del ciclo"}
            </h3>
            <p>
              Cuenta {a.login} · {a.server} · {a.environment}
            </p>
            <p>
              Armar inicia el loop; no envía una orden inmediata. Una entrada
              solo puede ocurrir si todos los requisitos del readiness vuelven
              a cumplir dentro del tick.
            </p>
            <button onClick={() => setConfirm("")}>Cancelar</button>
            <button
              className="danger"
              onClick={() => {
                onAction(confirm);
                setConfirm("");
              }}
            >
              Confirmar
            </button>
          </div>
        )}
        <p className="subtle">
          Apagar detiene el automatismo y conserva el ciclo. No liquida
          posiciones; para ello está Cerrar ciclo. El motor canónico conserva
          can_trade=false por defecto y este readiness no es una señal.
        </p>
        <details>
          <summary>Estado completo del servicio</summary>
          <pre>{JSON.stringify(b, null, 2)}</pre>
        </details>
      </section>
      <section className="panel">
        <div className="section-label">CUENTA Y CONDICIONES</div>
        <Row label="Cuenta" value={a.login} />
        <Row label="Servidor" value={a.server} />
        <Row label="Entorno" value={a.environment} />
        {a.environment === "REAL" && (
          <p className="notice danger">
            CUENTA REAL · las órdenes afectan fondos reales.
          </p>
        )}
        <Row label="Balance" value={num(a.balance, 2)} />
        <Row label="Equity" value={num(a.equity, 2)} />
        <hr />
        <Row label="Snapshot" value={b.snapshot ? "Publicado" : "Ausente"} />
        <Row
          label="Probabilidad"
          value={
            b.snapshot
              ? `${num(b.snapshot.probability * 100, 1)} %`
              : "No disponible"
          }
        />
        <Row label="Mínimo requerido" value="70 %" />
        <Row
          label="K / D M15"
          value={
            b.stochastic_m15
              ? `${num(b.stochastic_m15.k, 2)} / ${num(b.stochastic_m15.d, 2)}`
              : "No disponible"
          }
        />
        <Row
          label="Ciclo"
          value={
            cycle
              ? `${cycle.direction} · ${cycle.entries} entradas`
              : "Sin ciclo"
          }
        />
        <hr />
        <Row label="Lotes del ciclo" value="0.10 / 0.20 / 0.30" />
        <Row label="Cierre por beneficio" value="60 USD agregados" />
        <Row label="Límite de pérdida" value="3 % balance al armar" />
      </section>
    </div>
  );
}
function Positions({ state }) {
  return (
    <section className="panel">
      <div className="section-label">
        POSICIONES MT5 <span>{state.positions.length} abiertas</span>
      </div>
      {!state.positions.length ? (
        <Empty>Sin posiciones abiertas en la última consulta de MT5.</Empty>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {[
                  "Ticket",
                  "Símbolo",
                  "Dirección",
                  "Lotes",
                  "Apertura",
                  "Actual",
                  "P/L",
                  "Magic",
                ].map((x) => (
                  <th key={x}>{x}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {state.positions.map((p) => (
                <tr key={p.ticket}>
                  <td>{p.ticket}</td>
                  <td>{p.symbol}</td>
                  <td>{p.direction}</td>
                  <td>{p.volume}</td>
                  <td>{num(p.price_open)}</td>
                  <td>{num(p.price_current)}</td>
                  <td>{num(p.profit, 2)}</td>
                  <td>{p.magic}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
export function App() {
  const { state: rawState, error, refresh } = useFeed(),
    state =
      error || rawState.connection.status !== "READY"
        ? { ...rawState, engine: { ...rawState.engine, status: "STALE" } }
        : rawState,
    [tab, setTab] = useState("Mercado"),
    [tf, setTf] = useState("M15"),
    [pending, setPending] = useState(false),
    [message, setMessage] = useState(""),
    actionController = useRef(null);
  const action = async (name, { emergency = false } = {}) => {
    if (pending && !emergency) return;
    if (emergency) actionController.current?.abort();
    setPending(true);
    const controller = new AbortController();
    actionController.current = controller;
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const r = await fetch("/api/actions/" + name, {
          method: "POST",
          headers: { "X-ICT-Token": state.csrf_token ?? "" },
          signal: controller.signal,
        }),
        p = await r.json();
      if (!r.ok || !p.ok) throw Error(p.error ?? "Acción no completada");
      setMessage(p.message ?? "Acción completada: " + name);
      await refresh();
    } catch (e) {
      setMessage(e.name === "AbortError" ? "El bot no respondió a tiempo; el control fue liberado." : e.message);
    } finally {
      clearTimeout(timeout);
      if (actionController.current === controller) {
        actionController.current = null;
        setPending(false);
      }
    }
  };
  const emergencyDisarm = () => action("disarm", { emergency: true });
  const stale = error || state.connection.status !== "READY";
  return (
    <main>
      <header className="titlebar">
        <div className="brand">
          <strong>ICT</strong> SYSTEM <span>/ Terminal</span>
        </div>
        <div className="title-status">
          <Badge tone={stale ? "warn" : "good"}>
            {error ? "DESCONECTADO" : "MT5 · " + state.connection.status}
          </Badge>
          <span>{state.account?.environment ?? "SIN CUENTA"}</span>
          <span>{stamp(state.server_time)} Guayaquil</span>
        </div>
      </header>
      <nav aria-label="Pestañas de la terminal">
        {TABS.map((t) => (
          <button
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
        <button
          className="refresh"
          onClick={refresh}
          aria-label="Actualizar estado"
        >
          <RefreshCw size={15} />
        </button>
      </nav>
      {(stale || message) && (
        <div className="banner" role="status">
          {error ||
            state.connection.error ||
            (stale
              ? "Datos de mercado no vigentes. Verifica la conexión MT5."
              : message)}
          {message && (
            <button onClick={() => setMessage("")} aria-label="Cerrar mensaje">
              ×
            </button>
          )}
        </div>
      )}
      <div className="content">
        {tab === "Mercado" ? (
          <Market
            state={state}
            tf={tf}
            setTf={setTf}
            onAction={action}
            onBot={() => setTab("Bot mecánico")}
          />
        ) : tab === "ICT / Wyckoff" ? (
          <Evidence state={state} />
        ) : tab === "Bot mecánico" ? (
          <BotControl state={state} onAction={action} onEmergencyDisarm={emergencyDisarm} pending={pending} />
        ) : tab === "Posiciones" ? (
          <Positions state={state} />
        ) : (
          <Journal>
            <Events state={state} />
          </Journal>
        )}
      </div>
      <footer>
        <span>
          <Shield size={12} /> MT5 local · motor en observación ·{" "}
          {state.engine.status}
        </span>
        <span>
          Precio 1 s · velas 5 s · lectura {num(state.metrics?.reader_ms, 1)} ms
        </span>
      </footer>
    </main>
  );
}
