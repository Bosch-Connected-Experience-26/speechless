"""Demo scenarios for the visual dashboard.

Provides scripted sequences that exercise all system capabilities,
aligned with Requirement 16 (3-5 minute demo narrative).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from speechless.edge.intent_parser import IntentParser, VehicleIntent
from speechless.edge.simulated_vehicle import SimulatedVehicleControl
from speechless.router.classifier import CommandClassifier, CommandCategory


class NetworkCondition(Enum):
    """Simulated network conditions."""

    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass
class NetworkMetrics:
    """Simulated network metrics for dashboard display."""

    latency_ms: float = 50.0
    packet_loss: float = 0.0
    is_connected: bool = True
    condition: NetworkCondition = NetworkCondition.EXCELLENT

    @classmethod
    def excellent(cls) -> "NetworkMetrics":
        return cls(latency_ms=50, packet_loss=0.0, is_connected=True, condition=NetworkCondition.EXCELLENT)

    @classmethod
    def good(cls) -> "NetworkMetrics":
        return cls(latency_ms=120, packet_loss=0.01, is_connected=True, condition=NetworkCondition.GOOD)

    @classmethod
    def degraded(cls) -> "NetworkMetrics":
        return cls(latency_ms=500, packet_loss=0.05, is_connected=True, condition=NetworkCondition.DEGRADED)

    @classmethod
    def offline(cls) -> "NetworkMetrics":
        return cls(latency_ms=10000, packet_loss=1.0, is_connected=False, condition=NetworkCondition.OFFLINE)


@dataclass
class CommandResult:
    """Result of executing a demo command."""

    intent: str
    executed_on: str  # "edge" or "cloud"
    latency_ms: float
    success: bool
    response: str
    fallback_used: bool = False
    criticality: str = "normal"


@dataclass
class DemoCommand:
    """A single command in a demo scenario."""

    voice_text: str
    description: str
    network: NetworkMetrics
    expected_route: str  # "edge" or "cloud"
    delay_before: float = 1.0  # seconds to wait before this command
    delay_after: float = 0.5  # seconds to wait after execution
    # For speed/steering demo commands (not VehicleIntent-based)
    demo_action: Optional[str] = None  # "set_speed", "set_steering", "emergency_stop", "hazard"
    demo_value: Optional[float] = None


@dataclass
class DemoStats:
    """Aggregate statistics for the demo."""

    total_commands: int = 0
    edge_executions: int = 0
    cloud_executions: int = 0
    fallbacks_used: int = 0
    success_count: int = 0
    total_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_commands == 0:
            return 0.0
        return self.success_count / self.total_commands

    @property
    def avg_latency_ms(self) -> float:
        if self.total_commands == 0:
            return 0.0
        return self.total_latency_ms / self.total_commands

    def to_dict(self) -> dict:
        return {
            "total_commands": self.total_commands,
            "edge_executions": self.edge_executions,
            "cloud_executions": self.cloud_executions,
            "fallbacks_used": self.fallbacks_used,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
        }


class DemoScenarioRunner:
    """Runs scripted demo scenarios using Speechless components.

    Coordinates the simulated vehicle, intent parser, and classifier
    to produce realistic command execution results for the dashboard.

    Args:
        vehicle: SimulatedVehicleControl instance.
        on_log: Callback for log entries (level, message, metadata).
        on_state_update: Callback when dashboard state changes.
    """

    def __init__(
        self,
        vehicle: Optional[SimulatedVehicleControl] = None,
        on_log: Optional[Callable[[str, str, dict], None]] = None,
        on_state_update: Optional[Callable[[dict], None]] = None,
        kuksa_bridge: Optional[Any] = None,
    ) -> None:
        self.vehicle = vehicle or SimulatedVehicleControl()
        self.parser = IntentParser()
        self.classifier = CommandClassifier()
        self.on_log = on_log or (lambda *a: None)
        self.on_state_update = on_state_update or (lambda s: None)
        self.kuksa_bridge = kuksa_bridge
        self.stats = DemoStats()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def run_scenario(self, commands: list[DemoCommand]) -> None:
        """Execute a list of demo commands sequentially.

        Args:
            commands: Ordered list of DemoCommand to execute.
        """
        self._running = True
        self.stats = DemoStats()
        self.on_log("INFO", "Demo scenario started", {"total_commands": len(commands)})

        for cmd in commands:
            if not self._running:
                break

            await asyncio.sleep(cmd.delay_before)

            # Update network state
            self.on_state_update({
                "network_status": {
                    "latency_ms": cmd.network.latency_ms,
                    "packet_loss": cmd.network.packet_loss,
                    "is_connected": cmd.network.is_connected,
                }
            })
            self.on_log("NETWORK", f"Network: {cmd.network.condition.value}", {
                "latency_ms": cmd.network.latency_ms,
                "packet_loss": cmd.network.packet_loss,
            })

            # Execute command
            result = await self._execute_command(cmd)

            # Update stats
            self.stats.total_commands += 1
            if result.executed_on == "edge":
                self.stats.edge_executions += 1
            else:
                self.stats.cloud_executions += 1
            if result.success:
                self.stats.success_count += 1
            if result.fallback_used:
                self.stats.fallbacks_used += 1
            self.stats.total_latency_ms += result.latency_ms

            # Notify dashboard
            self.on_state_update({
                "current_command": {
                    "raw_text": cmd.voice_text,
                    "intent": result.intent,
                    "confidence": 0.95,
                    "criticality": result.criticality,
                },
                "routing_decision": {
                    "intent": result.intent,
                    "executed_on": result.executed_on,
                    "latency_ms": result.latency_ms,
                    "success": result.success,
                    "response": result.response,
                    "fallback_used": result.fallback_used,
                },
                "vehicle_state": self.vehicle.get_state(),
                "statistics": self.stats.to_dict(),
            })

            self.on_log("ROUTING", f"Executed on {result.executed_on}: {result.response}", {
                "intent": result.intent,
                "latency_ms": result.latency_ms,
            })

            await asyncio.sleep(cmd.delay_after)

        self._running = False
        self.on_log("INFO", "Demo scenario completed", self.stats.to_dict())

    def stop(self) -> None:
        """Stop the running scenario."""
        self._running = False

    async def _execute_command(self, cmd: DemoCommand) -> CommandResult:
        """Execute a single demo command."""
        start_time = time.perf_counter()

        # Handle demo-specific actions (speed, steering, emergency)
        if cmd.demo_action:
            return await self._execute_demo_action(cmd, start_time)

        # Try intent parsing first (vehicle control)
        intent = self.parser.parse(cmd.voice_text)

        if intent is not None:
            # Vehicle control command → edge
            result = self.vehicle.execute(intent)
            latency = (time.perf_counter() - start_time) * 1000

            self.on_log("VOICE", f"Parsed: {intent.system.value}/{intent.action.value}", {
                "text": cmd.voice_text,
            })

            # Also write to Kuksa if bridge is available
            if self.kuksa_bridge:
                try:
                    kuksa_op = await self.kuksa_bridge.write_intent(intent)
                    vss_msg = f"VSS: {kuksa_op.path} = {kuksa_op.value}"
                    if kuksa_op.success:
                        self.on_log("KUKSA", f"✅ {vss_msg} ({kuksa_op.latency_ms:.1f}ms)", {})
                    else:
                        self.on_log("KUKSA", f"⚠️ {vss_msg} (simulated)", {})
                except Exception:
                    pass  # Non-blocking — Kuksa is best-effort

            return CommandResult(
                intent=f"{intent.system.value}.{intent.action.value}",
                executed_on="edge",
                latency_ms=max(latency, 15.0),  # Min 15ms for realism
                success=result["success"],
                response=result["message"],
                criticality="high_priority",
            )

        # Informational command → cloud (simulated)
        classification = self.classifier.classify(cmd.voice_text)
        route = "cloud" if cmd.network.is_connected else "edge"

        # Simulate cloud latency
        if route == "cloud":
            await asyncio.sleep(cmd.network.latency_ms / 1000 * 2)  # Simulated round-trip
        else:
            await asyncio.sleep(0.05)  # Edge is fast

        latency = (time.perf_counter() - start_time) * 1000
        fallback = route != cmd.expected_route

        response = self._generate_cloud_response(cmd.voice_text, route)

        self.on_log("VOICE", f"Classified as {classification.category.value}", {
            "text": cmd.voice_text,
            "route": route,
        })

        return CommandResult(
            intent=f"informational.{self._extract_intent_name(cmd.voice_text)}",
            executed_on=route,
            latency_ms=latency,
            success=True,
            response=response,
            fallback_used=fallback,
            criticality="normal",
        )

    async def _execute_demo_action(self, cmd: DemoCommand, start_time: float) -> CommandResult:
        """Execute a demo-specific action (speed, steering, etc.)."""
        action = cmd.demo_action
        value = cmd.demo_value

        if action == "set_speed":
            result = self.vehicle.set_speed(value or 0)
            intent_name = "vehicle.accelerate"
            criticality = "safety_critical"
        elif action == "set_steering":
            result = self.vehicle.set_steering(value or 0)
            intent_name = "vehicle.steer"
            criticality = "safety_critical"
        elif action == "emergency_stop":
            result = self.vehicle.emergency_stop()
            intent_name = "vehicle.emergency_brake"
            criticality = "safety_critical"
        elif action == "hazard":
            result = self.vehicle.toggle_hazard_lights(bool(value))
            intent_name = "vehicle.hazard_lights"
            criticality = "high_priority"
        else:
            result = {"success": False, "message": f"Unknown demo action: {action}"}
            intent_name = "unknown"
            criticality = "normal"

        latency = (time.perf_counter() - start_time) * 1000

        self.on_log("VOICE", f"Demo action: {action}", {"text": cmd.voice_text, "value": value})

        return CommandResult(
            intent=intent_name,
            executed_on="edge",
            latency_ms=max(latency, 8.0),  # Safety-critical: ultra-fast
            success=result["success"],
            response=result["message"],
            criticality=criticality,
        )

    @staticmethod
    def _generate_cloud_response(voice_text: str, route: str) -> str:
        """Generate a simulated response for informational queries."""
        text_lower = voice_text.lower()

        if route == "edge":
            # Offline fallback
            if "food" in text_lower or "restaurant" in text_lower or "hungry" in text_lower:
                return "I'm offline. What type of cuisine do you prefer? I can help narrow it down."
            if "pasta" in text_lower or "seafood" in text_lower:
                return "Seafood pasta — great choice. Any price range preference?"
            if "mid-range" in text_lower or "fancy" in text_lower:
                return "Got it — mid-range seafood pasta. I'll find options when back online."
            return "Processing locally. I can help with basic queries while offline."

        # Cloud responses
        if "food" in text_lower or "restaurant" in text_lower or "hungry" in text_lower:
            return "Found 3 options: Pasta Perfetto (4.5★, 18min), Golden Dragon (4.2★, 8min), Casa Taco (4.0★, 15min)"
        if "route" in text_lower or "navigate" in text_lower:
            return "Route calculated. ETA: 18 minutes via A9 highway."
        if "gas" in text_lower or "fuel" in text_lower or "price" in text_lower:
            return "Shell A9: 2.35 EUR/L (updated 3 min ago). Total M9: 2.41 EUR/L."
        if "weather" in text_lower:
            return "Currently 22°C, partly cloudy. No rain expected today."
        return f"Cloud: Processed query about '{voice_text[:30]}...'"

    @staticmethod
    def _extract_intent_name(text: str) -> str:
        """Extract a short intent name from voice text."""
        text_lower = text.lower()
        if "food" in text_lower or "restaurant" in text_lower or "hungry" in text_lower:
            return "food_search"
        if "route" in text_lower or "navigate" in text_lower:
            return "navigation"
        if "gas" in text_lower or "fuel" in text_lower or "price" in text_lower:
            return "fuel_price"
        if "weather" in text_lower:
            return "weather"
        return "general_query"


def build_demo_scenario() -> list[DemoCommand]:
    """Build the full 3-5 minute demo scenario.

    Scenes:
    1. Highway — food query (cloud, excellent network)
    2. Speed up — vehicle acceleration (edge, safety-critical)
    3. Set temperature — HVAC control (edge)
    4. Tunnel entry — offline transition
    5-6. Offline follow-ups — multi-turn conversation
    7. Tunnel exit — online restoration with enriched response
    8. Fuel constraint — route planning
    9. Gas price query — real-time data
    10. Emergency brake — safety-critical
    11. Resume — back to normal
    """
    return [
        # Scene 1: Highway, online — food query
        DemoCommand(
            voice_text="I'm hungry. What food options are nearby?",
            description="Food query — CLOUD (informational)",
            network=NetworkMetrics.excellent(),
            expected_route="cloud",
            delay_before=1.5,
            delay_after=1.5,
        ),
        # Scene 2: Accelerate on highway
        DemoCommand(
            voice_text="Accelerate to 120 kilometers per hour",
            description="Acceleration — EDGE (safety-critical)",
            network=NetworkMetrics.excellent(),
            expected_route="edge",
            delay_before=1.5,
            demo_action="set_speed",
            demo_value=120.0,
        ),
        # Scene 3: Temperature control
        DemoCommand(
            voice_text="Set temperature to 24 degrees",
            description="HVAC control — EDGE",
            network=NetworkMetrics.excellent(),
            expected_route="edge",
            delay_before=1.5,
        ),
        # Scene 4: Turn on lights
        DemoCommand(
            voice_text="Turn on the lights",
            description="Lights — EDGE",
            network=NetworkMetrics.good(),
            expected_route="edge",
            delay_before=1.0,
        ),
        # Scene 5: Entering tunnel — network degrades
        DemoCommand(
            voice_text="I'm in the mood for Italian specifically",
            description="Follow-up — EDGE (degraded network, pushed to edge)",
            network=NetworkMetrics.degraded(),
            expected_route="edge",
            delay_before=2.0,
        ),
        # Scene 6: Fully offline in tunnel
        DemoCommand(
            voice_text="Preferably pasta with seafood",
            description="Offline follow-up (turn 2)",
            network=NetworkMetrics.offline(),
            expected_route="edge",
            delay_before=1.5,
        ),
        # Scene 7: Still offline
        DemoCommand(
            voice_text="Mid-range, nothing too fancy",
            description="Offline follow-up (turn 3)",
            network=NetworkMetrics.offline(),
            expected_route="edge",
            delay_before=1.5,
        ),
        # Scene 8: Exit tunnel — back online with enriched response
        DemoCommand(
            voice_text="Find me the best pasta restaurant nearby",
            description="Back online — CLOUD (enriched with offline context)",
            network=NetworkMetrics.excellent(),
            expected_route="cloud",
            delay_before=2.5,
            delay_after=2.0,
        ),
        # Scene 9: Fuel price query
        DemoCommand(
            voice_text="How much is gas at Shell A9?",
            description="Real-time fuel price — CLOUD",
            network=NetworkMetrics.excellent(),
            expected_route="cloud",
            delay_before=1.5,
        ),
        # Scene 10: Steer left
        DemoCommand(
            voice_text="Turn left 30 degrees",
            description="Steering — EDGE (safety-critical)",
            network=NetworkMetrics.excellent(),
            expected_route="edge",
            delay_before=1.5,
            demo_action="set_steering",
            demo_value=-30.0,
        ),
        # Scene 11: Straighten
        DemoCommand(
            voice_text="Straighten the wheel",
            description="Steering reset",
            network=NetworkMetrics.excellent(),
            expected_route="edge",
            delay_before=1.5,
            demo_action="set_steering",
            demo_value=0.0,
        ),
        # Scene 12: Emergency brake
        DemoCommand(
            voice_text="Stop the car immediately!",
            description="EMERGENCY BRAKE — EDGE (safety-critical, <50ms)",
            network=NetworkMetrics.excellent(),
            expected_route="edge",
            delay_before=2.0,
            demo_action="emergency_stop",
        ),
        # Scene 13: Resume (turn off hazards)
        DemoCommand(
            voice_text="Turn off hazard lights",
            description="Hazard lights off — EDGE",
            network=NetworkMetrics.excellent(),
            expected_route="edge",
            delay_before=2.0,
            demo_action="hazard",
            demo_value=0,
        ),
    ]
