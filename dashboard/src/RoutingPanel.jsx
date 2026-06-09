import React from "react";
import { labelFor } from "./signals.js";

// The challenge differentiator (R4): for every executed command, show whether
// the voice router sent it to EDGE or CLOUD and how long it took. Two latency
// numbers are shown distinctly (D11/D12): `latency_ms` is what the voice system
// REPORTS (it owns the routing decision); `bridge_ms` is what THIS bridge
// actually measured — one real, non-asserted datum.
//
// `latency_ms` scaled onto a 0..400ms bar; edge commands sit far left, cloud
// commands stretch right, making the hybrid split visible at a glance.
const SCALE_MS = 400;

function Lane({ route, latencyMs }) {
  const pct = Math.min(100, (Number(latencyMs ?? 0) / SCALE_MS) * 100);
  return (
    <div className={`lane ${route || "unknown"}`}>
      <div className="lane-fill" style={{ width: `${Math.max(pct, 4)}%` }} />
    </div>
  );
}

export default function RoutingPanel({ commands }) {
  return (
    <div className="panel routing">
      <div className="panel-head">
        <h2>Edge / Cloud routing</h2>
        <span className="hint">voice-reported · bridge-measured</span>
      </div>

      {commands.length === 0 && (
        <p className="empty">Waiting for commands… run <code>python poke.py</code> or speak to the assistant.</p>
      )}

      <ul className="cmd-list">
        {commands.map((c) => (
          <li key={c.id} className="cmd">
            <div className="cmd-top">
              <span className={`badge ${c.route || "unknown"}`}>{(c.route || "?").toUpperCase()}</span>
              <span className="cmd-intent">{c.intent || labelFor(c.path)}</span>
              <span className="cmd-latency">
                <strong>{c.latency_ms != null ? `${c.latency_ms}ms` : "—"}</strong>
                <small>{c.bridge_ms != null ? ` · bridge ${c.bridge_ms}ms` : ""}</small>
              </span>
            </div>
            <Lane route={c.route} latencyMs={c.latency_ms} />
          </li>
        ))}
      </ul>
    </div>
  );
}
