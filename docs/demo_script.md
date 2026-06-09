# Speechless Demo Script — Voice Assistant for Vehicle Control

## Team: LosRudos

## Duration: 3–5 minutes

## Overview

A single continuous narrative following a driver on a highway who:
1. Asks for food options (cloud AI)
2. Enters a tunnel losing connectivity (edge fallback)
3. Refines preferences via multi-turn offline conversation
4. Exits tunnel, gets enriched cloud response
5. Discovers fuel constraints on preferred option
6. Gets optimal route with refueling stop
7. Queries real-time gas prices
8. Experiences a biometric emergency (heart rate spike → hospital routing)

---

## System Architecture (shown before demo starts)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          SPEECHLESS                                  │
│                                                                     │
│   ┌──────────┐   ┌──────────┐   ┌────────────────────────────┐     │
│   │  Whisper  │──▶│ Keyword  │──▶│      Hybrid Router         │     │
│   │  STT     │   │ Classif. │   │  (edge/cloud, criticality) │     │
│   └──────────┘   └──────────┘   └──────────┬─────────────────┘     │
│                                             │                       │
│           ┌─────────────────────────────────┼───────────────┐       │
│           │                                 │               │       │
│           ▼                                 ▼               ▼       │
│   ┌───────────────┐              ┌──────────────────┐ ┌─────────┐  │
│   │ Edge LLM      │              │ AWS Bedrock      │ │Kuksa    │  │
│   │ (LM Studio /  │              │ (Claude, profile │ │gRPC     │  │
│   │  Jetson TRT)  │              │  "losrudos")     │ │:55555   │  │
│   └───────────────┘              └──────────────────┘ └─────────┘  │
│           │                                                         │
│   ┌───────────────┐   ┌──────────────┐   ┌──────────────────┐     │
│   │ Connectivity  │   │ Telemetry    │   │ Biometric        │     │
│   │ Monitor       │   │ (GPS, Fuel)  │   │ Monitor (HR)     │     │
│   └───────────────┘   └──────────────┘   └──────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
         │                     │                      │
         ▼                     ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Kuksa Vehicle Databroker (Docker, VSS)                  │
│  Vehicle.Cabin.HVAC.* │ Vehicle.CurrentLocation.* │ HeartRate       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Pre-Demo Setup

```bash
# Terminal 1: Start infrastructure
docker compose up -d

# Terminal 2: Start LM Studio (or verify Jetson endpoint)
# Ensure model loaded at http://localhost:1234/v1

# Terminal 3: Run the demo
uv run python scripts/run_demo.py
```

---

## Scene 1: Highway — Food Query (ONLINE, Cloud)

**Time: 0:00–0:30**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 1.1 | Driver | "Hey, I'm hungry. What food options are nearby?" | — |
| 1.2 | Classifier | Classify → INFORMATIONAL (no vehicle keywords) | `route=cloud` |
| 1.3 | Bedrock | converse API query with context "driver on highway, hungry" | — |
| 1.4 | TTS | Speaks response | "I found several options: Italian at Mario's (12 min), Chinese at Golden Dragon (8 min), and Mexican at Casa Taco (15 min). Would you like me to route to one?" |

**Key metrics shown:**
- Classification: <100ms
- Cloud response: ~2.5s
- End-to-end: <5s ✅

---

## Scene 2: Tunnel Entry — Offline Transition

**Time: 0:30–1:00**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 2.1 | ConnectivityMonitor | Ping fails (simulated tunnel) | State: ONLINE → OFFLINE |
| 2.2 | Pipeline | Mode switch | Processing mode: OFFLINE |
| 2.3 | TTS | Acknowledge | "Network connection lost. Switching to local processing." |
| 2.4 | Driver | "Actually, I'm in the mood for Italian specifically" | — |
| 2.5 | EdgeLLM | Handles locally (all routes → edge in OFFLINE) | — |
| 2.6 | ConvContext | Store turn 1 | `[{role: user, content: "Italian specifically"}]` |
| 2.7 | TTS | Local response | "Italian sounds great. Do you prefer pasta, pizza, or something else?" |

**Key metrics shown:**
- Connectivity detection: <5s ✅
- Edge LLM response: <3s ✅
- No cloud dependency

---

## Scene 3: In Tunnel — Multi-Turn Offline Conversation

**Time: 1:00–1:45**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 3.1 | Driver | "Pasta, definitely. Something with seafood." | — |
| 3.2 | EdgeLLM | Context-aware follow-up (turn 2) | "Seafood pasta — nice choice. Any price range preference?" |
| 3.3 | ConvContext | Accumulate | 2 turns stored |
| 3.4 | Driver | "Mid-range, nothing too fancy." | — |
| 3.5 | EdgeLLM | Context-aware (turn 3) | "Got it — mid-range Italian with seafood pasta. I'll find the best options when we're back online." |
| 3.6 | ConvContext | Accumulate | 3 turns stored ✅ (minimum 5 supported) |

**Key metrics shown:**
- Each turn: <3s response ✅
- Context maintained across all turns
- Contextually coherent responses without cloud

---

## Scene 4: Tunnel Exit — Online Restoration + Context Forwarding

**Time: 1:45–2:30**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 4.1 | ConnectivityMonitor | Ping succeeds | State: OFFLINE → ONLINE |
| 4.2 | Pipeline | Forward accumulated context to Bedrock | All 3 offline turns sent |
| 4.3 | Bedrock | Enriched response with real data + offline preferences | — |
| 4.4 | TTS | Speaks enriched result | "Welcome back online! Based on your preferences — mid-range Italian with seafood pasta — I found: Pasta Perfetto (4.5★, 18 min away, €15–25 range) and Trattoria del Mare (4.2★, 22 min, seafood specialist). Want me to route to one?" |

**Key metrics shown:**
- Reconnection detection: <5s ✅
- Context forwarding: all turns preserved ✅
- Enriched response combines offline preferences + cloud data ✅

---

## Scene 5: Fuel Constraint Discovery

**Time: 2:30–3:00**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 5.1 | Driver | "Route me to Pasta Perfetto" | — |
| 5.2 | Classifier | INFORMATIONAL → cloud (route planning needs cloud) | `route=cloud` |
| 5.3 | TelemetryReader | Read from Kuksa: GPS, fuel_level (15%), consumption (8.5 L/100km) | `{lat: 48.12, lon: 11.55, fuel: 15%, rate: 8.5}` |
| 5.4 | RoutePlanner | compute_range_km() → ~88km remaining range | — |
| 5.5 | RoutePlanner | is_reachable("Pasta Perfetto", 95km) → FALSE | — |
| 5.6 | TTS | Alert | "⚠️ Pasta Perfetto is 95km away but your fuel range is approximately 88km. You'll need to refuel first. Shall I find gas stations along the way?" |

**Key metrics shown:**
- Telemetry read: real-time from Kuksa VSS ✅
- Fuel computation: Haversine distance vs. range ✅
- Proactive warning before running out of fuel ✅

---

## Scene 6: Optimal Route with Constraints

**Time: 3:00–3:30**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 6.1 | Driver | "Yes, find me a gas station on the way" | — |
| 6.2 | RoutePlanner | compute_route_with_constraints(fuel_stop=True, destination="Pasta Perfetto") | — |
| 6.3 | RoutePlanner | rank_routes() → least deviation first | `[{station: "Shell A9", deviation: 2.3km}, {station: "Total Hbf", deviation: 5.1km}]` |
| 6.4 | TTS | Present optimal | "Optimal route: Refuel at Shell A9 (2.3km deviation), then continue to Pasta Perfetto. Total additional time: 8 minutes. Total deviation: 2.3km." |

**Key metrics shown:**
- Multi-constraint satisfaction ✅
- Ranked by deviation (least first) ✅
- Presents deviation + time metadata ✅

---

## Scene 7: Real-Time Gas Price Query

**Time: 3:30–3:50**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 7.1 | Driver | "How much is gas at Shell A9?" | — |
| 7.2 | Classifier | INFORMATIONAL → cloud | `route=cloud` |
| 7.3 | CloudProcessor | Query real-time fuel prices | — |
| 7.4 | TTS | Response with source + timestamp | "Current price at Shell A9 is 2.35 EUR per liter. Source: real-time pricing, updated 3 minutes ago." |

**Key metrics shown:**
- Real-time data with source attribution ✅
- Local currency (EUR) ✅
- Freshness timestamp ✅

---

## Scene 8: Vehicle Control Interlude (Edge Speed Demo)

**Time: 3:50–4:10**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 8.1 | Driver | "Set temperature to 22 degrees" | — |
| 8.2 | Classifier | VEHICLE_CONTROL (keywords: "temperature", "set") | `route=edge`, confidence: 0.9 |
| 8.3 | IntentParser | Parse → HVAC, SET_TEMPERATURE, {temperature: 22} | — |
| 8.4 | VehicleController | Write VSS: `Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature` = 22 | — |
| 8.5 | TTS | Confirm | "Temperature set to 22 degrees." |

**Key metrics shown:**
- Full pipeline: <1s (edge, no cloud round-trip) ✅
- Real Kuksa VSS actuation ✅
- Instant confirmation ✅

---

## Scene 9: Biometric Emergency

**Time: 4:10–4:45**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 9.1 | BiometricMonitor | Read HR from Kuksa: 185 BPM (threshold: 180) | CRITICAL ✅ |
| 9.2 | BiometricMonitor | Fire on_emergency callback | — |
| 9.3 | RoutePlanner | Emergency route: nearest hospital | `{hospital: "Klinikum München", ETA: 8 min}` |
| 9.4 | TTS | Emergency alert (louder, urgent tone) | "⚠️ EMERGENCY: Elevated heart rate detected — 185 BPM. Routing to nearest hospital: Klinikum München, estimated arrival 8 minutes. Please pull over if possible." |
| 9.5 | — | Wait 25 seconds... | — |
| 9.6 | BiometricMonitor | HR drops to 75 BPM (< 180 within 30s) | Cancel emergency |
| 9.7 | TTS | Cancellation | "Heart rate has normalized to 75 BPM. Emergency routing cancelled. Resuming normal navigation to Pasta Perfetto via Shell A9." |

**Key metrics shown:**
- 5s sampling interval ✅
- Threshold detection: HR ≥ 180 → emergency ✅
- Auto-cancellation within 30s window ✅
- Returns to previous route context ✅

---

## Scene 10: Wrap-Up

**Time: 4:45–5:00**

| Step | Actor | Action | Expected Output |
|------|-------|--------|-----------------|
| 10.1 | Demo | Print performance summary | — |
| 10.2 | Summary | Show stats | Total commands: 8, Edge: 3, Cloud: 5, Avg latency: 1.2s, Success: 100% |
| 10.3 | Summary | Show routing decisions log | Each command with classification, route, latency |

---

## Performance Targets (shown in summary)

| Metric | Target | Demo Result |
|--------|--------|-------------|
| Vehicle control end-to-end | <1s | ✅ |
| Informational query response start | <5s | ✅ |
| Connectivity detection | <5s | ✅ |
| Edge LLM offline response | <3s | ✅ |
| Classification latency | <100ms | ✅ |
| Biometric sampling | every 5s | ✅ |
| Emergency cancellation window | 30s | ✅ |
| Offline follow-up turns | ≥5 supported | ✅ |

---

## Technical Highlights for Evaluators

1. **Edge-first architecture** — Vehicle control never touches the cloud. Safety commands execute in <50ms on edge.

2. **Connectivity-aware seamless transitions** — Periodic ping detection, automatic mode switch, context preservation across boundaries.

3. **Context forwarding** — Offline conversation isn't lost. All turns forward to Bedrock on reconnection for enriched responses combining user preferences with real-time cloud data.

4. **Fuel-aware intelligence** — Real telemetry from Kuksa VSS feeds into Haversine-based reachability computation. Proactive warnings, not reactive failures.

5. **Multi-constraint route optimization** — Satisfies refuel + food stops with minimal deviation, ranked by total detour distance.

6. **Biometric safety net** — Continuous heart rate monitoring with emergency auto-routing and graceful cancellation. No false-alarm fatigue.

7. **Dual deployment targets** — Same OpenAI-compatible API for LM Studio (dev laptop) and NVIDIA Jetson (production car). Config switch only, zero code changes.

8. **Property-based testing** — 22 correctness properties validated with Hypothesis, ensuring invariants hold for any input, not just happy-path examples.

---

## Demo Commands Quick Reference

```
"I'm hungry. What food options are nearby?"          → Cloud (Bedrock)
"I'm in the mood for Italian specifically"           → Edge LLM (offline)
"Pasta, definitely. Something with seafood."         → Edge LLM (offline, turn 2)
"Mid-range, nothing too fancy."                      → Edge LLM (offline, turn 3)
"Route me to Pasta Perfetto"                         → Cloud + Telemetry
"Find me a gas station on the way"                   → Cloud + Route Planner
"How much is gas at Shell A9?"                       → Cloud (real-time data)
"Set temperature to 22 degrees"                      → Edge (vehicle control)
[Biometric spike simulated]                          → Emergency routing
[Biometric normalizes]                               → Emergency cancelled
```

---

## Failure Modes Demonstrated

| Failure | Handling | Demonstrated In |
|---------|----------|-----------------|
| Network loss | Graceful offline transition, local LLM fallback | Scene 2 |
| Destination out of fuel range | Proactive warning + refueling suggestion | Scene 5 |
| Heart rate critical | Emergency routing with auto-cancellation | Scene 9 |
| Cloud timeout | 5s timeout, inform driver | (can be shown if needed) |
| Kuksa disconnection | Exponential backoff, 3 retries | (integration test) |
