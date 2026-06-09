import React, { useEffect, useState } from "react";
import Car from "./Car.jsx";
import RoutingPanel from "./RoutingPanel.jsx";
import { P, on } from "./signals.js";
import { useVehicleSocket } from "./useVehicleSocket.js";

function Gauge({ label, value, unit, max, accent }) {
  const pct = max ? Math.min(100, (Number(value || 0) / max) * 100) : 0;
  return (
    <div className="gauge">
      <div className="gauge-label">{label}</div>
      <div className="gauge-value">
        {value ?? "—"}
        <span className="gauge-unit">{unit}</span>
      </div>
      {max != null && (
        <div className="gauge-bar">
          <div className="gauge-fill" style={{ width: `${pct}%`, background: accent }} />
        </div>
      )}
    </div>
  );
}

export default function App() {
  const { signals, commands, status, setValue } = useVehicleSocket();
  const [mode, setMode] = useState("…");

  // Show whether the bridge is talking to a real Kuksa databroker or simulating.
  useEffect(() => {
    let alive = true;
    const poll = () =>
      fetch("/healthz")
        .then((r) => r.json())
        .then((d) => alive && setMode(d.kuksa_connected ? "Kuksa (live)" : d.mode))
        .catch(() => alive && setMode("offline"));
    poll();
    const t = setInterval(poll, 4000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const ac = on(signals[P.ac]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◆</span>
          <div>
            <h1>LosRudos</h1>
            <p>Voice Assistant for Vehicle Control · BCX26</p>
          </div>
        </div>
        <div className="status-cluster">
          <span className={`pill ${status}`}>{status === "open" ? "● live" : `○ ${status}`}</span>
          <span className="pill mode">{mode}</span>
        </div>
      </header>

      <main className="layout">
        <section className="stage">
          <Car signals={signals} onSet={setValue} />
          <p className="stage-hint">click parts of the car to actuate them manually</p>
        </section>

        <aside className="side">
          <div className="gauges">
            <Gauge label="Speed" value={signals[P.speed] ?? 0} unit="km/h" max={200} accent="#5ad1ff" />
            <Gauge
              label="Battery"
              value={signals[P.battery] ?? 0}
              unit="%"
              max={100}
              accent="#7CFFB2"
            />
            <Gauge label="Cabin" value={signals[P.temp] ?? "—"} unit="°C" />
            <div className={`gauge ac ${ac ? "on" : ""}`}>
              <div className="gauge-label">A/C</div>
              <div className="gauge-value">{ac ? "ON" : "OFF"}</div>
            </div>
          </div>
          <RoutingPanel commands={commands} />
        </aside>
      </main>
    </div>
  );
}
