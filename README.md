# Hybrid Voice Assistant for Vehicle Control

A hybrid AI-powered in-vehicle voice assistant that intelligently routes commands between edge and cloud systems to enable fast, reliable, real-time vehicle control.

## Problem Statement

In-vehicle voice control today relies entirely on cloud connectivity — introducing latency and single points of failure for safety-critical commands.

## Solution

A hybrid voice assistant that intelligently splits workloads between edge and cloud to control vehicle APIs in real-time, using agentic AI patterns for latency-aware decision-making.

## Architecture

```
Voice Input → Intent Parser → Hybrid Router → Vehicle Control
                                  ↓
                    ┌─────────────┴─────────────┐
                    │                           │
              Edge Executor              Cloud Executor
              (Jetson Nano)              (Google Cloud)
              • Brake        <50ms       • Route finding   200ms
              • Accelerate               • Search
              • Steering                 • Analysis
              • Hazard lights
              • Climate
```

### Routing Logic

| Command Type | Execution | Latency | Example |
|---|---|---|---|
| Safety-critical | Edge only | <50ms | "Stop the car" |
| Vehicle control | Edge primary | <50ms | "Turn on hazard lights" |
| Complex reasoning | Cloud primary | ~200ms | "Route me to airport" |
| Network degraded | Fallback to edge | <50ms | Any command offline |

## Quick Start

```bash
# Clone
git clone <your-repo-url>
cd hybrid-voice-assistant

# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Run visual dashboard
python run_visual_dashboard.py
# Open http://localhost:5001 → Click "▶ Start Demo"

# Or run CLI demo
python run_hybrid_voice_assistant_demo.py
```

## Project Structure

```
├── src/alpacai/core/voice_assistant/
│   ├── hybrid_router.py       # Edge-cloud routing decisions
│   ├── intent_parser.py       # Voice → structured commands
│   └── vehicle_control.py     # Vehicle abstraction (sim + KUKSA)
├── run_visual_dashboard.py    # Web dashboard with live car visualization
├── run_hybrid_voice_assistant_demo.py  # CLI demo
├── docker/                    # KUKSA vehicle server
├── requirements.txt
└── pyproject.toml
```

## Features

- **Sub-50ms response** for safety-critical commands (edge execution)
- **Network-aware routing** — adapts to connectivity conditions in real-time
- **Automatic fallback** — commands always succeed via edge when cloud unavailable
- **Visual dashboard** — real-time car visualization, gauge speedometer, routing history
- **Production-ready** — deployable on NVIDIA Jetson Nano for in-vehicle use

## Visual Dashboard

The web dashboard shows:
- Top-down car with steering wheel rotation and brake/hazard lights
- Gauge-style speedometer (0–200 km/h with color zones)
- Real-time routing decisions (edge vs cloud)
- Network status with signal bars
- Live event log with color-coded entries

## Voice Commands Supported

**Safety-Critical (Edge):**
- "Stop the car" / "Brake"
- "Accelerate to 80 km/h"
- "Turn left 30 degrees"

**Vehicle Control (Edge):**
- "Turn on hazard lights"
- "Set temperature to 22 degrees"
- "Volume up"

**Complex (Cloud):**
- "Route me to the airport"
- "Find a nearby restaurant"

## Deployment

### Local Development
```bash
pip install -e .
python run_visual_dashboard.py
```

### Jetson Nano (Edge)
```bash
pip install -e .
python run_visual_dashboard.py  # Access from http://<jetson-ip>:5001
```

### With KUKSA Vehicle Server
```bash
cd docker && docker-compose up -d
pip install -e ".[vehicle]"
```

## License

MIT
