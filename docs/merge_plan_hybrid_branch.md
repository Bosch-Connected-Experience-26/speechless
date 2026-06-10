# Merge Plan: hybrid-voice-assistant → agent-setup

## Strategy

**Do NOT `git merge`.** The branches have incompatible structures (`src/alpacai/core/` vs `speechless/`). Instead, cherry-pick useful concepts and port them into the existing architecture.

---

## What to Take

| From Hybrid Branch | Port Into | Priority |
|-------------------|-----------|----------|
| `SimulatedVehicleControl` (in-memory vehicle state) | `speechless/edge/simulated_vehicle.py` | HIGH — needed for demo |
| `CommandSafetyCriticality` enum + tiered routing | `speechless/router/classifier.py` | MEDIUM — enriches demo narrative |
| `NetworkMonitor.update_metrics()` (latency/packet loss) | `speechless/connectivity/monitor.py` | LOW — optional for demo simulation |
| Decision logging + `get_stats()` | `speechless/utils/logging.py` / `main.py` | HIGH — demo summary output |
| Demo runner script pattern (async scenarios) | `scripts/run_demo.py` | HIGH — the actual demo |
| Architecture ASCII diagram | Already in `docs/demo_script.md` | DONE |

## What to Discard

| From Hybrid Branch | Reason |
|-------------------|--------|
| `requirements.txt` | We use `pyproject.toml` + `uv` |
| `docker/Dockerfile` | Not needed; `docker-compose.yml` suffices |
| `docker/docker-compose.yml` | Ours is better (healthchecks, named volumes) |
| `src/alpacai/` namespace | Dead; our package is `speechless` |
| `sys.path.insert(0, ...)` hacks | `uv run` handles PYTHONPATH |
| `VoiceIntentParser` (their intent parser) | Ours is more complete and Kuksa-aligned |
| `run_visual_dashboard.py` | Stretch goal only if time permits |

---

## Implementation Steps

### Step 1: Create SimulatedVehicleControl

**File:** `speechless/edge/simulated_vehicle.py`

Port the in-memory state machine from the hybrid branch's `vehicle_control.py`. Adapt to accept `VehicleIntent` objects (our existing type) instead of raw strings.

```python
@dataclass
class VehicleState:
    temperature: float = 22.0
    window_position: int = 0  # 0=closed, 100=open
    doors_locked: bool = True
    lights_on: bool = False
    speed: float = 0.0
    hazard_lights: bool = False
    commands_executed: int = 0

class SimulatedVehicleControl:
    """In-memory vehicle simulator for demo and testing."""
    
    def execute(self, intent: VehicleIntent) -> ActuationResult:
        """Execute intent against simulated state."""
        ...
    
    def get_state(self) -> dict:
        """Return current vehicle state for display."""
        ...
```

**Tests:** `tests/test_simulated_vehicle.py` — verify state changes for each intent type.

---

### Step 2: Add Safety Criticality to Router

**File:** `speechless/router/classifier.py`

Add:
```python
class CommandCriticality(Enum):
    SAFETY_CRITICAL = "safety_critical"  # Future: brake, steer
    HIGH_PRIORITY = "high_priority"      # HVAC, lights, locks
    NORMAL = "normal"                     # Informational queries
```

Update `ClassificationResult`:
```python
@dataclass
class ClassificationResult:
    category: CommandCategory
    confidence: float
    criticality: CommandCriticality  # NEW
    matched_keywords: list[str]
```

All current vehicle control commands → `HIGH_PRIORITY`. Informational → `NORMAL`.

---

### Step 3: Add Performance Tracking to Pipeline

**File:** `speechless/main.py`

Add to `PipelineOrchestrator`:
```python
@dataclass
class CommandDecision:
    transcription: str
    classification: str
    route: str
    latency_ms: float
    success: bool
    fallback_used: bool = False

class PipelineOrchestrator:
    def __init__(self, ...):
        ...
        self._decision_log: list[CommandDecision] = []
    
    def get_stats(self) -> dict:
        """Return aggregate performance stats for demo summary."""
        ...
```

---

### Step 4: Create Demo Runner Script

**File:** `scripts/run_demo.py`

Structure (adapted from hybrid branch pattern):
```python
#!/usr/bin/env python3
"""Speechless Demo Runner — 3-5 minute scripted scenario."""

import asyncio
from speechless.edge.simulated_vehicle import SimulatedVehicleControl
from speechless.edge.intent_parser import IntentParser
from speechless.router.classifier import CommandClassifier
from speechless.connectivity.monitor import ConnectivityMonitor
from speechless.main import PipelineOrchestrator
...

async def run_demo():
    # Scene 1: Highway food query (ONLINE)
    # Scene 2: Tunnel entry (OFFLINE transition)
    # Scene 3: Multi-turn offline conversation
    # Scene 4: Tunnel exit (ONLINE restoration)
    # Scene 5: Fuel constraint
    # Scene 6: Optimal route
    # Scene 7: Gas price query
    # Scene 8: Vehicle control (edge speed)
    # Scene 9: Biometric emergency
    # Summary: print stats

if __name__ == "__main__":
    asyncio.run(run_demo())
```

---

### Step 5: Docker Compose — Keep Current (Better)

Your current `docker-compose.yml` already uses:
- `ghcr.io/eclipse-kuksa/kuksa-databroker:0.4.4` ✅
- Named volumes ✅
- Healthchecks with `grpc_health_probe` ✅

The hybrid branch's `docker/docker-compose.yml` likely uses heavier/older images. No action needed.

---

## Execution Order (for demo tomorrow)

| # | Action | Time Estimate | Blocks Demo? |
|---|--------|---------------|--------------|
| 1 | Create `simulated_vehicle.py` + test | 15 min | YES |
| 2 | Create `scripts/run_demo.py` (basic version) | 30 min | YES |
| 3 | Add performance stats to pipeline | 15 min | Improves demo |
| 4 | Add criticality enum | 10 min | Nice to have |
| 5 | Test full demo flow end-to-end | 20 min | YES |

**Total estimated: ~1.5 hours for a working demo.**

---

## After Demo (Cleanup)

- Remove `hybrid-voice-assistant` branch (it's fully subsumed)
- Add property tests for `SimulatedVehicleControl`
- Consider visual dashboard if hackathon continues
