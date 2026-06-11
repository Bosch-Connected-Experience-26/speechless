"""Kuksa databroker bridge for the visual dashboard.

Provides a non-blocking interface that:
1. Attempts to connect to the running Kuksa databroker
2. Writes VSS signals when vehicle commands execute
3. Reads telemetry (GPS, fuel, heart rate) for display
4. Falls back gracefully when Kuksa is unavailable

The dashboard shows real VSS paths being actuated in real-time,
proving the system talks to a real automotive data layer.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from speechless.edge.intent_parser import VehicleIntent
from speechless.edge.vehicle_controller import VehicleController


@dataclass
class VSSOperation:
    """Record of a VSS signal operation for dashboard display."""

    timestamp: str
    path: str
    value: Any
    type: str
    operation: str  # "write" or "read"
    success: bool
    latency_ms: float
    error: str | None = None


@dataclass
class KuksaStatus:
    """Current Kuksa connection status."""

    connected: bool = False
    host: str = "localhost"
    port: int = 55556
    last_check: str | None = None
    operations_count: int = 0
    errors_count: int = 0


class KuksaBridge:
    """Bridge between the dashboard and Kuksa databroker.

    Wraps VehicleController to add operation tracking and graceful
    fallback. Every VSS write/read is logged for dashboard display.

    Args:
        host: Kuksa databroker hostname.
        port: Kuksa databroker gRPC port.
        auto_connect: Whether to attempt connection on init.
    """

    # Additional VSS paths for telemetry display (read-only)
    TELEMETRY_PATHS: dict[str, str] = {
        "gps_latitude": "Vehicle.CurrentLocation.Latitude",
        "gps_longitude": "Vehicle.CurrentLocation.Longitude",
        "fuel_level": "Vehicle.Powertrain.FuelSystem.Level",
        "fuel_consumption": "Vehicle.Powertrain.FuelSystem.InstantConsumption",
        "heart_rate": "Vehicle.Occupant.Row1.DriverSide.HeartRate",
        "speed": "Vehicle.Speed",
    }

    def __init__(
        self,
        host: str = "localhost",
        port: int = 55556,
        auto_connect: bool = True,
    ) -> None:
        self._controller = VehicleController(kuksa_host=host, kuksa_port=port)
        self._status = KuksaStatus(host=host, port=port)
        self._operations: list[VSSOperation] = []
        self._max_operations = 50
        self._telemetry_cache: dict[str, Any] = {}

        if auto_connect:
            self._try_connect_sync()

    @property
    def status(self) -> KuksaStatus:
        """Current connection status."""
        return self._status

    @property
    def is_connected(self) -> bool:
        """Whether Kuksa databroker is reachable."""
        return self._status.connected

    @property
    def operations(self) -> list[VSSOperation]:
        """Recent VSS operations (newest first)."""
        return self._operations

    def get_status_dict(self) -> dict:
        """Return status as a serializable dict for the dashboard API."""
        return {
            "connected": self._status.connected,
            "host": self._status.host,
            "port": self._status.port,
            "last_check": self._status.last_check,
            "operations_count": self._status.operations_count,
            "errors_count": self._status.errors_count,
        }

    def get_operations_dict(self) -> list[dict]:
        """Return recent operations as serializable list."""
        return [
            {
                "timestamp": op.timestamp,
                "path": op.path,
                "value": str(op.value),
                "type": op.type,
                "operation": op.operation,
                "success": op.success,
                "latency_ms": op.latency_ms,
                "error": op.error,
            }
            for op in self._operations[:20]  # Last 20 for display
        ]

    def get_telemetry_dict(self) -> dict:
        """Return cached telemetry values."""
        return dict(self._telemetry_cache)

    async def write_intent(self, intent: VehicleIntent) -> VSSOperation:
        """Write a vehicle intent to Kuksa and record the operation.

        If Kuksa is not connected, records the operation as failed
        but returns the VSS path that would have been written (for display).

        Args:
            intent: The vehicle control intent to actuate.

        Returns:
            VSSOperation with the result.
        """
        signal = self._controller.intent_to_signal(intent)
        if signal is None:
            op = VSSOperation(
                timestamp=datetime.now().isoformat(),
                path="(unmapped)",
                value=None,
                type="",
                operation="write",
                success=False,
                latency_ms=0.0,
                error=f"No VSS mapping for {intent.system.value}/{intent.action.value}",
            )
            self._record_operation(op)
            return op

        start = time.perf_counter()

        if self._status.connected:
            try:
                result = await self._controller.actuate(intent)
                latency = (time.perf_counter() - start) * 1000
                op = VSSOperation(
                    timestamp=datetime.now().isoformat(),
                    path=signal.path,
                    value=signal.value,
                    type=signal.type,
                    operation="write",
                    success=result.success,
                    latency_ms=latency,
                    error=result.error_message,
                )
            except Exception as e:
                latency = (time.perf_counter() - start) * 1000
                op = VSSOperation(
                    timestamp=datetime.now().isoformat(),
                    path=signal.path,
                    value=signal.value,
                    type=signal.type,
                    operation="write",
                    success=False,
                    latency_ms=latency,
                    error=str(e),
                )
        else:
            # Not connected — record what WOULD have been written
            op = VSSOperation(
                timestamp=datetime.now().isoformat(),
                path=signal.path,
                value=signal.value,
                type=signal.type,
                operation="write",
                success=False,
                latency_ms=0.0,
                error="Kuksa not connected (simulated mode)",
            )

        self._record_operation(op)
        return op

    async def read_telemetry(self) -> dict[str, Any]:
        """Read telemetry values from Kuksa (or return cached/simulated).

        Returns:
            Dict mapping telemetry names to their current values.
        """
        if not self._status.connected:
            # Return simulated telemetry for demo
            return self._simulated_telemetry()

        for name, path in self.TELEMETRY_PATHS.items():
            start = time.perf_counter()
            try:
                if self._controller._client:
                    values = self._controller._client.get_current_values([path])
                    value = self._unwrap_datapoint(values.get(path))
                    self._telemetry_cache[name] = value
                    latency = (time.perf_counter() - start) * 1000
                    op = VSSOperation(
                        timestamp=datetime.now().isoformat(),
                        path=path,
                        value=value,
                        type="read",
                        operation="read",
                        success=True,
                        latency_ms=latency,
                    )
                    self._record_operation(op)
            except Exception:
                pass  # Graceful — use cached or simulated

        return dict(self._telemetry_cache) if self._telemetry_cache else self._simulated_telemetry()

    @staticmethod
    def _unwrap_datapoint(value: Any) -> Any:
        return getattr(value, "value", value)

    def try_reconnect(self) -> bool:
        """Attempt to reconnect to Kuksa (non-blocking check)."""
        return self._try_connect_sync()

    def _try_connect_sync(self) -> bool:
        """Synchronous connection attempt (best-effort)."""
        self._status.last_check = datetime.now().isoformat()
        try:
            from kuksa_client.grpc import VSSClient  # type: ignore[import-untyped]

            client = VSSClient(self._status.host, self._status.port)
            client.connect()
            self._controller._client = client
            self._controller._connected = True
            self._status.connected = True
            return True
        except Exception:
            self._status.connected = False
            return False

    def _record_operation(self, op: VSSOperation) -> None:
        """Record an operation and update counters."""
        self._operations.insert(0, op)
        if len(self._operations) > self._max_operations:
            self._operations.pop()
        self._status.operations_count += 1
        if not op.success:
            self._status.errors_count += 1

    @staticmethod
    def _simulated_telemetry() -> dict[str, Any]:
        """Return simulated telemetry values for demo when Kuksa is unavailable."""
        return {
            "gps_latitude": 48.1351,
            "gps_longitude": 11.5820,
            "fuel_level": 15.0,
            "fuel_consumption": 8.5,
            "heart_rate": 72,
            "speed": 0.0,
        }
