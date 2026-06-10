"""Vehicle backend abstractions for the dashboard."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from speechless.edge.intent_parser import VehicleIntent
from speechless.edge.simulated_vehicle import SimulatedVehicleControl
from speechless.edge.vehicle_controller import VehicleController, VSSSignal
from speechless.models import AppConfig


@dataclass
class BackendOperation:
    """Dashboard-facing vehicle signal operation."""

    timestamp: str
    path: str
    value: Any
    type: str
    operation: str
    success: bool
    latency_ms: float
    error: str | None = None

    def to_dict(self) -> dict:
        """Return a JSON-serializable operation."""
        return {
            "timestamp": self.timestamp,
            "path": self.path,
            "value": str(self.value),
            "type": self.type,
            "operation": self.operation,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class VehicleBackend(Protocol):
    """Backend contract used by dashboard interaction and demo modes."""

    name: str
    vehicle: SimulatedVehicleControl

    @property
    def is_connected(self) -> bool:
        """Whether the backing vehicle data service is connected."""

    async def execute_intent(self, intent: VehicleIntent) -> dict:
        """Execute a parsed vehicle intent."""

    def get_vehicle_state(self) -> dict:
        """Return serializable vehicle state."""

    def get_status_dict(self) -> dict:
        """Return backend status."""

    def get_operations_dict(self) -> list[dict]:
        """Return recent backend operations."""

    def get_telemetry_dict(self) -> dict:
        """Return backend telemetry values."""

    def try_reconnect(self) -> bool:
        """Attempt backend reconnection when supported."""


class SimulatedVehicleBackend:
    """In-memory vehicle backend for local development and tests."""

    name = "simulated"

    def __init__(self, vehicle: SimulatedVehicleControl | None = None) -> None:
        self.vehicle = vehicle or SimulatedVehicleControl()
        self._controller = VehicleController()
        self._operations: list[BackendOperation] = []
        self._max_operations = 50

    @property
    def is_connected(self) -> bool:
        """The simulated backend does not require an external connection."""
        return True

    async def execute_intent(self, intent: VehicleIntent) -> dict:
        """Execute a vehicle intent against simulated state and record VSS output."""
        start = time.perf_counter()
        result = self.vehicle.execute(intent)
        latency = (time.perf_counter() - start) * 1000
        signal = self._controller.intent_to_signal(intent)
        self._record_signal(signal, result["success"], latency)
        return result

    def get_vehicle_state(self) -> dict:
        """Return the simulated vehicle state."""
        return self.vehicle.get_state()

    def get_status_dict(self) -> dict:
        """Return simulated backend status."""
        return {
            "connected": True,
            "host": "simulated",
            "port": None,
            "last_check": datetime.now().isoformat(),
            "operations_count": len(self._operations),
            "errors_count": sum(1 for op in self._operations if not op.success),
            "backend": self.name,
        }

    def get_operations_dict(self) -> list[dict]:
        """Return recent simulated VSS operations."""
        return [op.to_dict() for op in self._operations[:20]]

    def get_telemetry_dict(self) -> dict:
        """Return telemetry derived from simulated state."""
        state = self.vehicle.state
        return {
            "gps_latitude": 48.1351,
            "gps_longitude": 11.5820,
            "fuel_level": 15.0,
            "fuel_consumption": 8.5,
            "heart_rate": 72,
            "speed": state.speed,
        }

    def try_reconnect(self) -> bool:
        """No-op reconnect for simulated backend."""
        return True

    def _record_signal(
        self,
        signal: VSSSignal | None,
        success: bool,
        latency_ms: float,
    ) -> None:
        if signal is None:
            op = BackendOperation(
                timestamp=datetime.now().isoformat(),
                path="(unmapped)",
                value=None,
                type="",
                operation="write",
                success=False,
                latency_ms=latency_ms,
                error="No VSS mapping for intent",
            )
        else:
            op = BackendOperation(
                timestamp=datetime.now().isoformat(),
                path=signal.path,
                value=signal.value,
                type=signal.type,
                operation="write",
                success=success,
                latency_ms=latency_ms,
            )
        self._operations.insert(0, op)
        if len(self._operations) > self._max_operations:
            self._operations.pop()


class KuksaVehicleBackend:
    """Kuksa-backed vehicle backend with simulated state fallback."""

    name = "kuksa"

    def __init__(self, config: AppConfig, vehicle: SimulatedVehicleControl | None = None) -> None:
        from speechless.dashboard.kuksa_bridge import KuksaBridge

        self.vehicle = vehicle or SimulatedVehicleControl()
        self.kuksa_bridge = KuksaBridge(
            host=config.kuksa_host,
            port=config.kuksa_port,
            auto_connect=True,
        )

    @property
    def is_connected(self) -> bool:
        """Whether Kuksa is currently connected."""
        return self.kuksa_bridge.is_connected

    async def execute_intent(self, intent: VehicleIntent) -> dict:
        """Execute in simulated state and mirror the VSS write to Kuksa."""
        result = self.vehicle.execute(intent)
        await self.kuksa_bridge.write_intent(intent)
        return result

    def get_vehicle_state(self) -> dict:
        """Return simulated state used for dashboard visualization."""
        return self.vehicle.get_state()

    def get_status_dict(self) -> dict:
        """Return Kuksa status with backend metadata."""
        status = self.kuksa_bridge.get_status_dict()
        status["backend"] = self.name
        return status

    def get_operations_dict(self) -> list[dict]:
        """Return Kuksa operation history."""
        return self.kuksa_bridge.get_operations_dict()

    def get_telemetry_dict(self) -> dict:
        """Return Kuksa telemetry cache or simulated telemetry fallback."""
        telemetry = self.kuksa_bridge.get_telemetry_dict()
        if telemetry:
            return telemetry
        return self.kuksa_bridge._simulated_telemetry()

    def try_reconnect(self) -> bool:
        """Attempt to reconnect to Kuksa."""
        return self.kuksa_bridge.try_reconnect()


def create_vehicle_backend(config: AppConfig, backend: str) -> VehicleBackend:
    """Factory for dashboard vehicle backends."""
    if backend == "simulated":
        return SimulatedVehicleBackend()
    if backend == "kuksa":
        return KuksaVehicleBackend(config)
    raise ValueError(f"Unsupported vehicle backend: {backend}")
