"""Vehicle controller with Kuksa gRPC integration.

Translates parsed VehicleIntents into VSS (Vehicle Signal Specification)
signals and actuates them via the Kuksa databroker gRPC interface.
Includes exponential backoff reconnection on connection failures.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from speechless.edge.intent_parser import Action, VehicleIntent, VehicleSystem
from speechless.utils.retry import RetryConfig, compute_backoff_delay


@dataclass
class VSSSignal:
    """A Vehicle Signal Specification path and value."""

    path: str
    value: Any
    type: str  # "int32", "uint8", "float", "boolean", "string"


@dataclass
class ActuationResult:
    """Result of a vehicle signal actuation."""

    success: bool
    signal: VSSSignal
    error_message: Optional[str] = None


class VehicleController:
    """Translates intents to Kuksa gRPC calls via VSS paths.

    Maintains a connection to the Kuksa databroker and handles
    reconnection with exponential backoff (up to 3 retries).

    Args:
        kuksa_host: Kuksa databroker hostname.
        kuksa_port: Kuksa databroker gRPC port.
    """

    VSS_MAPPING: dict[tuple[str, str], VSSSignal] = {
        ("hvac", "set_temperature"): VSSSignal(
            path="Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature",
            value=None,
            type="int32",
        ),
        ("windows", "open"): VSSSignal(
            path="Vehicle.Cabin.Door.Row1.DriverSide.Window.Position",
            value=100,
            type="uint8",
        ),
        ("windows", "close"): VSSSignal(
            path="Vehicle.Cabin.Door.Row1.DriverSide.Window.Position",
            value=0,
            type="uint8",
        ),
        ("doors", "lock"): VSSSignal(
            path="Vehicle.Cabin.Door.Row1.DriverSide.IsLocked",
            value=True,
            type="boolean",
        ),
        ("doors", "unlock"): VSSSignal(
            path="Vehicle.Cabin.Door.Row1.DriverSide.IsLocked",
            value=False,
            type="boolean",
        ),
        ("lights", "turn_on"): VSSSignal(
            path="Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling",
            value=True,
            type="boolean",
        ),
        ("lights", "turn_off"): VSSSignal(
            path="Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling",
            value=False,
            type="boolean",
        ),
    }

    def __init__(self, kuksa_host: str = "localhost", kuksa_port: int = 55556):
        self.kuksa_host = kuksa_host
        self.kuksa_port = kuksa_port
        self._client: Any = None
        self._connected = False
        self._retry_config = RetryConfig(max_retries=3, base_delay=1.0, multiplier=2.0)

    def intent_to_signal(self, intent: VehicleIntent) -> Optional[VSSSignal]:
        """Map a VehicleIntent to the corresponding VSS signal.

        Args:
            intent: Parsed vehicle control intent.

        Returns:
            VSSSignal with the correct path and value, or None if unmapped.
        """
        key = (intent.system.value, intent.action.value)
        signal_template = self.VSS_MAPPING.get(key)
        if signal_template is None:
            return None

        # For temperature, inject the parameter value
        if intent.action == Action.SET_TEMPERATURE:
            return VSSSignal(
                path=signal_template.path,
                value=intent.parameters.get("temperature", 22),
                type=signal_template.type,
            )
        return VSSSignal(
            path=signal_template.path,
            value=signal_template.value,
            type=signal_template.type,
        )

    @staticmethod
    def format_vss_path(path: str) -> str:
        """Validate and format a VSS path string.

        A valid VSS path must:
        - Start with "Vehicle."
        - Have at least 3 dot-separated segments
        - Contain only alphanumeric characters in each segment

        Args:
            path: VSS path string to validate.

        Returns:
            The validated path (unchanged if valid).

        Raises:
            ValueError: If path doesn't meet VSS format requirements.
        """
        if not path.startswith("Vehicle."):
            raise ValueError(f"Invalid VSS path: must start with 'Vehicle.': {path}")
        parts = path.split(".")
        if len(parts) < 3:
            raise ValueError(f"Invalid VSS path: must have at least 3 segments: {path}")
        import re
        for part in parts:
            if not re.match(r"^[A-Za-z0-9]+$", part):
                raise ValueError(
                    f"Invalid VSS path: segment '{part}' contains invalid characters: {path}"
                )
        return path

    def generate_error_message(self, error: Exception, intent: VehicleIntent) -> str:
        """Generate a user-friendly error message for a failed actuation.

        The error message always includes the system name and action name
        for context.

        Args:
            error: The exception that occurred.
            intent: The VehicleIntent that failed.

        Returns:
            Human-readable error description.
        """
        system_name = intent.system.value.replace("_", " ")
        action_name = intent.action.value.replace("_", " ")
        return (
            f"Unable to {action_name} the {system_name}. "
            f"Reason: {type(error).__name__}: {str(error)}"
        )

    async def connect(self) -> bool:
        """Connect to Kuksa databroker with exponential backoff.

        Returns:
            True if connection established, False after exhausting retries.
        """
        last_error: Optional[Exception] = None
        for attempt in range(self._retry_config.max_retries + 1):
            try:
                # kuksa-client connection (lazy import to avoid hard dependency in tests)
                from kuksa_client.grpc import VSSClient  # type: ignore[import-untyped]

                self._client = VSSClient(self.kuksa_host, self.kuksa_port)
                self._client.connect()
                self._connected = True
                return True
            except Exception as e:
                last_error = e
                if attempt < self._retry_config.max_retries:
                    delay = compute_backoff_delay(attempt, self._retry_config)
                    time.sleep(delay)

        self._connected = False
        return False

    async def actuate(self, intent: VehicleIntent) -> ActuationResult:
        """Execute a vehicle control intent via Kuksa gRPC.

        Args:
            intent: Parsed vehicle control intent.

        Returns:
            ActuationResult indicating success or failure.
        """
        signal = self.intent_to_signal(intent)
        if signal is None:
            return ActuationResult(
                success=False,
                signal=VSSSignal(path="", value=None, type=""),
                error_message=f"No VSS mapping for {intent.system.value}/{intent.action.value}",
            )

        try:
            if not self._connected:
                connected = await self.connect()
                if not connected:
                    return ActuationResult(
                        success=False,
                        signal=signal,
                        error_message="Failed to connect to Kuksa databroker",
                    )

            # Write the signal value via Kuksa gRPC
            self._client.set_current_values({signal.path: signal.value})
            return ActuationResult(success=True, signal=signal)

        except Exception as e:
            error_msg = self.generate_error_message(e, intent)
            return ActuationResult(success=False, signal=signal, error_message=error_msg)
