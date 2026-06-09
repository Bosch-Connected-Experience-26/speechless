# Hybrid Voice Assistant for Vehicle Control

A hybrid AI-powered in-vehicle voice assistant that intelligently routes commands between edge and cloud systems to enable fast, reliable, real-time vehicle control. Fully integrated with **Eclipse Kuksa Vehicle API** (VSS/gRPC).

## Team

**LosRudos** — *Voice-driven intelligence for the road ahead*

| Name | GitHub Handle |
|---|---|
| | [@kronos-cm](https://github.com/kronos-cm) |
| | [@jesusalc](https://github.com/jesusalc) |
| | [@carloshled](https://github.com/carloshled) |

**Challenge:** Voice Assistant for Vehicle Control — Future Mobility (Automotive), BCW26

## Problem Statement

In-vehicle voice control today relies entirely on cloud connectivity — introducing latency and single points of failure for safety-critical commands.

## Solution

A hybrid voice assistant that intelligently splits workloads between edge and cloud to control vehicle APIs in real-time, using agentic AI patterns for latency-aware decision-making.

## Architecture

```
Voice Input → Intent Parser → Hybrid Router → Vehicle Control (Kuksa VSS)
                                  ↓
                    ┌─────────────┴─────────────┐
                    │                           │
              Edge Executor              Cloud Executor
              (Jetson Nano)              (Cloud LLM)
              • Brake        <50ms       • Route finding   200ms
              • Accelerate               • Search
              • Steering                 • Analysis
              • Hazard lights
              • Climate / HVAC
```

See [doc/architecture.md](doc/architecture.md) for detailed Mermaid diagrams.

### Routing Logic

| Command Type | Execution | Latency | Example |
|---|---|---|---|
| Safety-critical | Edge only | <50ms | "Stop the car" |
| Vehicle control | Edge primary | <50ms | "Turn on hazard lights" |
| Complex reasoning | Cloud primary | ~200ms | "Route me to airport" |
| Network degraded | Fallback to edge | <50ms | Any command offline |

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for Kuksa databroker)

### Setup

```bash
# Clone
git clone https://github.com/Bosch-Connected-Experience-26/speechless.git
cd speechless
git checkout hybrid-voice-assistant

# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install kuksa-client  # For Kuksa integration
```

### Start Kuksa Databroker

```bash
docker compose -f docker/docker-compose.yml up -d
# Or use the agent-setup docker-compose:
# docker compose up -d
```

This starts Eclipse Kuksa Databroker on `localhost:55555` (gRPC).

### Run

```bash
# CLI demo (simulated vehicle)
python run_hybrid_voice_assistant_demo.py

# CLI demo with real Kuksa databroker
python run_hybrid_voice_assistant_demo.py --kuksa

# Visual web dashboard (simulated)
python run_visual_dashboard.py
# Open http://localhost:5001 → Click "▶ Start Demo"

# Visual web dashboard with Kuksa
python run_visual_dashboard.py --kuksa
```

## Project Structure

```
├── src/alpacai/core/voice_assistant/
│   ├── hybrid_router.py       # Edge-cloud routing engine
│   ├── intent_parser.py       # Voice → structured commands (regex + params)
│   └── vehicle_control.py     # Vehicle abstraction (SimulatedVehicleControl + KuksaVehicleControl)
├── run_visual_dashboard.py    # Flask web dashboard with SVG car visualization
├── run_hybrid_voice_assistant_demo.py  # CLI demo with 3 network scenarios
├── doc/
│   ├── architecture.md        # Mermaid architecture diagrams
│   └── img/                   # Rendered PNG diagrams
├── docker/
│   ├── docker-compose.yml     # Kuksa databroker container
│   └── Dockerfile
├── requirements.txt
└── pyproject.toml
```

## Features

- **Sub-50ms response** for safety-critical commands (edge execution)
- **Kuksa VSS integration** — writes real vehicle signals to Eclipse Kuksa Databroker via gRPC
- **Network-aware routing** — adapts to connectivity conditions in real-time
- **Automatic fallback** — commands always succeed via edge when cloud unavailable
- **Visual dashboard** — real-time car visualization, gauge speedometer, routing history
- **3 network scenarios** — normal, degraded, offline with automatic mode switching
- **Production-ready** — deployable on NVIDIA Jetson Nano for in-vehicle use

## Kuksa Integration

When running with `--kuksa`, voice commands write directly to the Eclipse Kuksa Databroker:

| VSS Signal Path | Description | Example Command |
|---|---|---|
| `Vehicle.Speed` | Vehicle speed (km/h) | "Accelerate to 80" |
| `Vehicle.Chassis.SteeringWheel.Angle` | Steering angle (degrees) | "Turn left 30 degrees" |
| `Vehicle.Chassis.Brake.PedalPosition` | Brake pedal (0-100%) | "Stop the car" |
| `Vehicle.Body.Lights.Hazard.IsSignaling` | Hazard lights (bool) | "Turn on hazard lights" |
| `Vehicle.Cabin.HVAC.AmbientAirTemperature` | Cabin temperature (°C) | "Set temperature to 22" |
| `Vehicle.Cabin.Infotainment.Media.Volume` | Audio volume (0-100) | "Volume up" |

## Visual Dashboard

The web dashboard (port 5001) shows:
- Top-down SVG car with steering rotation, brake/hazard lights animation
- Gauge-style speedometer (0–200 km/h with green/orange/red zones)
- Real-time routing decisions (edge vs cloud) with history dots
- Network status with rising signal bars
- Live event log with color-coded entries (INFO, VOICE, ROUTING, NETWORK, ERROR)

## Voice Commands Supported

**Safety-Critical (Edge Only):**
- "Stop the car" / "Brake"
- "Accelerate to 80 km/h"
- "Turn left 30 degrees"

**Vehicle Control (Edge Primary):**
- "Turn on hazard lights"
- "Set temperature to 22 degrees"
- "Volume up" / "Increase volume"

**Complex Reasoning (Cloud Primary):**
- "Route me to the airport"
- "Find a nearby restaurant"

## Deployment

### Local Development (no Kuksa)
```bash
pip install -e .
python run_visual_dashboard.py
```

### With Kuksa Databroker
```bash
docker compose -f docker/docker-compose.yml up -d
pip install -e ".[vehicle]"
python run_visual_dashboard.py --kuksa
```

### Jetson Nano (Edge Production)
```bash
pip install -e ".[vehicle]"
python run_visual_dashboard.py --kuksa  # Access from http://<jetson-ip>:5001
```

## License

MIT
