import React from "react";
import { P, on } from "./signals.js";

// Top-down car. Each controllable element is an SVG layer; signal state toggles
// a CSS class and styles.css drives the glow/blink/position (D6). Clicking a
// part sends a `set` to the bridge, so the dashboard is bidirectional — you can
// demo it by hand without the voice pipeline.
export default function Car({ signals, onSet }) {
  const low = on(signals[P.lowBeam]);
  const high = on(signals[P.highBeam]);
  const indL = on(signals[P.indLeft]) || on(signals[P.hazard]);
  const indR = on(signals[P.indRight]) || on(signals[P.hazard]);
  const lockedD = on(signals[P.lockDriver]);
  const lockedP = on(signals[P.lockPass]);
  const doorOpen = on(signals[P.doorDriverOpen]);
  const winPos = Math.min(Math.max(Number(signals[P.windowDriver] ?? 0), 0), 100); // open %
  const glassH = 150 * (1 - winPos / 100); // closed window = full glass

  const toggle = (path, cur) => onSet(path, !on(cur));

  return (
    <svg className="car" viewBox="0 0 260 480" role="img" aria-label="vehicle">
      <defs>
        <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3a4256" />
          <stop offset="0.5" stopColor="#2a3142" />
          <stop offset="1" stopColor="#1d2230" />
        </linearGradient>
        <linearGradient id="beamGrad" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#fff4c2" stopOpacity="0.85" />
          <stop offset="1" stopColor="#fff4c2" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* headlight beams (forward = up); brighter on high beam */}
      <g className={`beams ${low ? "on" : ""} ${high ? "high" : ""}`}>
        <polygon className="beam" points="92,58 110,58 134,2 50,2" />
        <polygon className="beam" points="150,58 168,58 210,2 126,2" />
      </g>

      {/* wheels */}
      <g className="wheels">
        <rect x="40" y="96" width="18" height="56" rx="8" />
        <rect x="202" y="96" width="18" height="56" rx="8" />
        <rect x="40" y="330" width="18" height="56" rx="8" />
        <rect x="202" y="330" width="18" height="56" rx="8" />
      </g>

      {/* body */}
      <rect className="body" x="52" y="44" width="156" height="392" rx="46" fill="url(#bodyGrad)" />

      {/* glass: windshield, roof, rear window */}
      <polygon className="glass" points="82,150 178,150 168,116 92,116" />
      <rect className="glass roof" x="74" y="150" width="112" height="180" rx="20" />
      <polygon className="glass" points="92,330 168,330 160,360 100,360" />

      {/* driver window (left cabin edge): glass height shrinks as it opens */}
      <g className="window" onClick={() => onSet(P.windowDriver, winPos > 0 ? 0 : 60)}>
        <title>Driver window ({winPos}% open) — click to toggle</title>
        <rect className="window-frame" x="70" y="158" width="12" height="150" rx="4" />
        <rect className="window-glass" x="70" y="158" width="12" height={glassH} rx="4" />
      </g>

      {/* driver door (left): swings open on the hinge when IsOpen */}
      <g
        className={`door ${doorOpen ? "open" : ""}`}
        onClick={() => toggle(P.doorDriverOpen, signals[P.doorDriverOpen])}
        style={{ transformOrigin: "82px 168px" }}
      >
        <title>Driver door — click to {doorOpen ? "close" : "open"}</title>
        <rect x="70" y="168" width="14" height="132" rx="6" />
      </g>

      {/* headlights */}
      <g className={`lights front ${low ? "on" : ""}`} onClick={() => toggle(P.lowBeam, signals[P.lowBeam])}>
        <title>Headlights — click to toggle</title>
        <rect x="86" y="56" width="30" height="15" rx="6" />
        <rect x="144" y="56" width="30" height="15" rx="6" />
      </g>

      {/* turn indicators (amber, blink) */}
      <rect
        className={`indicator ${indL ? "on" : ""}`}
        x="58" y="58" width="14" height="13" rx="4"
        onClick={() => toggle(P.indLeft, signals[P.indLeft])}
      />
      <rect
        className={`indicator ${indR ? "on" : ""}`}
        x="188" y="58" width="14" height="13" rx="4"
        onClick={() => toggle(P.indRight, signals[P.indRight])}
      />
      <rect className={`indicator ${indL ? "on" : ""}`} x="58" y="410" width="14" height="13" rx="4" />
      <rect className={`indicator ${indR ? "on" : ""}`} x="188" y="410" width="14" height="13" rx="4" />

      {/* taillights (always lit red) */}
      <g className="lights rear">
        <rect x="86" y="410" width="30" height="14" rx="6" />
        <rect x="144" y="410" width="30" height="14" rx="6" />
      </g>

      {/* lock badges — driver (left) and passenger (right), each clickable */}
      {[
        { x: 92, locked: lockedD, path: P.lockDriver, label: "Driver door" },
        { x: 142, locked: lockedP, path: P.lockPass, label: "Passenger door" },
      ].map(({ x, locked, path, label }) => (
        <g
          key={path}
          className={`lock ${locked ? "locked" : "unlocked"}`}
          onClick={() => toggle(path, signals[path])}
          transform={`translate(${x} 232)`}
        >
          <title>{label} {locked ? "locked" : "unlocked"} — click to toggle</title>
          <rect className="lock-body" x="0" y="12" width="24" height="20" rx="4" />
          <path className="lock-shackle" d={locked ? "M5 12 v-5 a7 7 0 0 1 14 0 v5" : "M5 12 v-5 a7 7 0 0 1 14 0"} />
        </g>
      ))}

      {/* front marker */}
      <text className="front-label" x="130" y="34" textAnchor="middle">FRONT</text>
    </svg>
  );
}
