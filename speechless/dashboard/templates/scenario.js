/* ============================================================
   SPEECHLESS COCKPIT — scripted demo timeline
   Mirrors scenarios.py + demo_script.md as a cinematic beat list.
   Each step: { t:type, ...params, d:dwell_ms_after }
   Latencies are in ms. The engine formats + drives all visuals.
   ============================================================ */
window.SPEECHLESS_SCENARIO = [

  /* ---------- SCENE 1 · Highway food query → CLOUD ---------- */
  { t:'scene', n:1, name:'Highway · Food Query' },
  { t:'net', cond:'excellent', d:300 },
  { t:'map', dest:'Searching…', eta:'—', dist:'—', next:'A9 · Munich', prog:0.05 },
  { t:'vehicle', set:{ speed:96, headlights:true }, d:600 },
  { t:'driver', text:"I'm hungry — what are my food options nearby?", d:300 },
  { t:'route', to:'cloud', intent:'informational.food_search', cls:'INFORMATIONAL', crit:'normal', lat:2380, d:200 },
  { t:'vss', op:'read', path:'Vehicle.CurrentLocation.Latitude', value:'48.1351', lat:9.2, ok:true },
  { t:'poi', id:'food', lit:true },
  { t:'assistant', text:"Three good spots: Pasta Perfetto — 4.5★, 18 min. Golden Dragon — 4.2★, 8 min. Casa Taco — 4.0★, 15 min.", d:1700 },

  /* ---------- SCENE 2 · Climate set → EDGE ---------- */
  { t:'scene', n:2, name:'Cabin Climate · Edge' },
  { t:'driver', text:"Set the temperature to 24 degrees.", d:200 },
  { t:'route', to:'edge', intent:'hvac.set_temperature', cls:'VEHICLE CONTROL', crit:'high', lat:31, d:120 },
  { t:'vehicle', set:{ temperature:24 } },
  { t:'vss', op:'write', path:'Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature', value:'24', lat:12.4, ok:true },
  { t:'chip', id:'chip-climate', flash:true },
  { t:'assistant', text:"Done — cabin set to 24 degrees.", d:1300 },

  /* ---------- SCENE 3 · Accelerate → EDGE (safety) ---------- */
  { t:'scene', n:3, name:'Acceleration · Edge Safety' },
  { t:'driver', text:"Accelerate to 120 kilometers per hour.", d:200 },
  { t:'route', to:'edge', intent:'vehicle.accelerate', cls:'SAFETY-CRITICAL', crit:'safety', lat:18, d:120 },
  { t:'vehicle', set:{ speed:120 }, d:200 },
  { t:'vss', op:'write', path:'Vehicle.Speed', value:'120', lat:8.1, ok:true },
  { t:'assistant', text:"Accelerating to 120. Executed on-device in 18 milliseconds.", d:1600 },

  /* ---------- SCENE 4 · Tunnel entry → OFFLINE fallback ---------- */
  { t:'scene', n:4, name:'Tunnel · Connection Lost' },
  { t:'map', prog:0.30, eta:18, dist:14.2, dest:'Pasta Perfetto' },
  { t:'tunnel', on:true, d:400 },
  { t:'net', cond:'offline', d:300 },
  { t:'mood', m:'offline', d:200 },
  { t:'assistant', text:"Signal lost in the tunnel — switching to local processing.", d:900 },
  { t:'driver', text:"Actually, I'm in the mood for Italian specifically.", d:200 },
  { t:'route', to:'edge', intent:'edge_llm.preference', cls:'OFFLINE · LOCAL LLM', crit:'normal', lat:1180, fallback:true, d:120 },
  { t:'assistant', text:"Italian it is. Pasta, pizza, or something else?", d:1400 },

  /* ---------- SCENE 5 · Offline multi-turn (turn 2) ---------- */
  { t:'scene', n:5, name:'Offline · Multi-turn Context' },
  { t:'driver', text:"Pasta — something with seafood.", d:200 },
  { t:'route', to:'edge', intent:'edge_llm.preference', cls:'OFFLINE · CONTEXT 2/3', crit:'normal', lat:1340, fallback:true, d:120 },
  { t:'assistant', text:"Seafood pasta — great pick. Any price range?", d:1300 },

  /* ---------- SCENE 6 · Offline multi-turn (turn 3) ---------- */
  { t:'driver', text:"Mid-range, nothing too fancy.", d:200 },
  { t:'route', to:'edge', intent:'edge_llm.preference', cls:'OFFLINE · CONTEXT 3/3', crit:'normal', lat:1260, fallback:true, d:120 },
  { t:'assistant', text:"Got it — mid-range seafood pasta. I'll finalize the moment we're back online.", d:1500 },

  /* ---------- SCENE 7 · Tunnel exit → CLOUD enriched ---------- */
  { t:'scene', n:7, name:'Reconnected · Context Forwarding' },
  { t:'map', prog:0.52 },
  { t:'tunnel', on:false },
  { t:'net', cond:'excellent', d:300 },
  { t:'mood', m:'normal', d:200 },
  { t:'driver', text:"Find me the best one.", d:200 },
  { t:'route', to:'cloud', intent:'informational.food_search+', cls:'ENRICHED · 3 OFFLINE TURNS', crit:'normal', lat:2510, d:120 },
  { t:'vss', op:'read', path:'Vehicle.CurrentLocation.Longitude', value:'11.5820', lat:8.8, ok:true },
  { t:'assistant', text:"Welcome back. Matching your offline picks: Pasta Perfetto — 4.5★, seafood specialist, €15–25, 18 min away. Route there?", d:1900 },

  /* ---------- SCENE 8 · Fuel constraint → CLOUD + telemetry ---------- */
  { t:'scene', n:8, name:'Fuel-Aware Routing' },
  { t:'driver', text:"Yes — route me to Pasta Perfetto.", d:200 },
  { t:'route', to:'cloud', intent:'navigation.route_plan', cls:'TELEMETRY + ROUTE', crit:'normal', lat:1980, d:120 },
  { t:'vss', op:'read', path:'Vehicle.Powertrain.FuelSystem.Level', value:'15%', lat:7.4, ok:true },
  { t:'vss', op:'read', path:'Vehicle.Powertrain.FuelSystem.InstantConsumption', value:'8.5', lat:7.9, ok:true },
  { t:'fuel', pct:15, range:'~88 km', low:true, d:200 },
  { t:'assistant', text:"Heads up — Pasta Perfetto is 95 km away but your range is about 88 km. You'll need fuel first. Find a station en route?", d:1900 },

  /* ---------- SCENE 9 · Gas station → route planner ---------- */
  { t:'scene', n:9, name:'Multi-constraint Route' },
  { t:'driver', text:"Yes, find a gas station on the way.", d:200 },
  { t:'route', to:'cloud', intent:'navigation.route_constrained', cls:'RANKED · MIN DEVIATION', crit:'normal', lat:2140, d:120 },
  { t:'poi', id:'gas', lit:true },
  { t:'map', prog:0.62, eta:26, dist:18.7, next:'Shell A9 · refuel' },
  { t:'assistant', text:"Optimal route: refuel at Shell A9 — only 2.3 km detour — then on to Pasta Perfetto. Adds 8 minutes.", d:1800 },

  /* ---------- SCENE 10 · Gas price → CLOUD realtime ---------- */
  { t:'scene', n:10, name:'Real-time Data' },
  { t:'driver', text:"How much is gas at Shell A9?", d:200 },
  { t:'route', to:'cloud', intent:'informational.fuel_price', cls:'REAL-TIME · SOURCED', crit:'normal', lat:1760, d:120 },
  { t:'assistant', text:"Shell A9 is 2.35 € per litre — live pricing, updated 3 minutes ago.", d:1600 },

  /* ---------- SCENE 11 · Steering → EDGE ---------- */
  { t:'scene', n:11, name:'Steering · Edge' },
  { t:'driver', text:"Take the exit — steer left 30 degrees.", d:200 },
  { t:'route', to:'edge', intent:'vehicle.steer', cls:'SAFETY-CRITICAL', crit:'safety', lat:14, d:120 },
  { t:'vehicle', set:{ steering:-30, speed:64 }, d:200 },
  { t:'vss', op:'write', path:'Vehicle.Chassis.SteeringWheel.Angle', value:'-30', lat:9.0, ok:true },
  { t:'assistant', text:"Steering left, easing off the throttle.", d:1100 },
  { t:'vehicle', set:{ steering:0, speed:58 }, d:600 },

  /* ---------- SCENE 12 · Emergency brake → EDGE snap ---------- */
  { t:'scene', n:12, name:'Emergency Brake · <50ms' },
  { t:'driver', text:"Stop the car — now!", d:120 },
  { t:'route', to:'edge', intent:'vehicle.emergency_brake', cls:'SAFETY-CRITICAL', crit:'safety', lat:11, d:60 },
  { t:'brake' },
  { t:'vss', op:'write', path:'Vehicle.ADAS.EBA.IsActive', value:'true', lat:6.2, ok:true },
  { t:'assistant', text:"Emergency stop — executed on-device in 11 milliseconds. Hazards on.", d:1800 },

  /* ---------- SCENE 13 · Biometric emergency → red flood ---------- */
  { t:'scene', n:13, name:'Biometric Emergency' },
  { t:'hr', bpm:185, state:'CRITICAL', alert:true, d:200 },
  { t:'mood', m:'emergency', d:200 },
  { t:'vss', op:'read', path:'Vehicle.Occupant.Row1.DriverSide.HeartRate', value:'185', lat:7.1, ok:true },
  { t:'alert', on:true, title:'ELEVATED HEART RATE — 185 BPM', sub:'Routing to nearest hospital · Klinikum München · ETA 8 min' },
  { t:'poi', id:'hosp', lit:true },
  { t:'map', dest:'Klinikum München', eta:8, dist:6.1, next:'EMERGENCY ROUTE', prog:0.66 },
  { t:'assistant', text:"Elevated heart rate detected — 185 BPM. Rerouting to Klinikum München, 8 minutes. Please pull over if you can.", d:2400 },

  /* ---------- SCENE 14 · Normalize → cancel ---------- */
  { t:'scene', n:14, name:'Recovery · Auto-cancel' },
  { t:'hr', bpm:78, state:'Normal', alert:false, d:200 },
  { t:'vss', op:'read', path:'Vehicle.Occupant.Row1.DriverSide.HeartRate', value:'78', lat:7.0, ok:true },
  { t:'alert', on:false },
  { t:'mood', m:'normal', d:200 },
  { t:'assistant', text:"Heart rate normalized to 78 BPM. Emergency cancelled — resuming route to Pasta Perfetto via Shell A9.", d:1800 },

  /* ---------- SCENE 15 · Wrap-up ---------- */
  { t:'scene', n:15, name:'Demo Complete' },
  { t:'phase', p:'idle' },
  { t:'orbstatus', text:'ALL SYSTEMS NOMINAL' },
  { t:'assistant', text:"That's the full hybrid loop — edge for safety, cloud for intelligence, seamless across the gap.", d:600 },
  { t:'summary' },
];
