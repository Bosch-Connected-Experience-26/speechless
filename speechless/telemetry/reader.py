"""Telemetry reader for GPS, fuel, and biometric data via Kuksa VSS.

Reads vehicle telemetry data from the Kuksa databroker using standard
VSS (Vehicle Signal Specification) paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class VehicleTelemetry:
    """Current vehicle telemetry snapshot."""

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    fuel_level: Optional[float] = None  # percentage (0-100)
    fuel_consumption: Optional[float] = None  # liters per 100km
    heart_rate: Optional[int] = None  # BPM


class TelemetryReader:
    """Reads vehicle telemetry data from Kuksa databroker via gRPC.

    Uses standard VSS paths for GPS position, fuel status, and biometrics.
    Handles read failures gracefully by returning None for individual readings.

    Args:
        kuksa_host: Kuksa databroker hostname.
        kuksa_port: Kuksa databroker gRPC port.
    """

    VSS_PATHS = {
        "latitude": "Vehicle.CurrentLocation.Latitude",
        "longitude": "Vehicle.CurrentLocation.Longitude",
        "fuel_level": "Vehicle.Powertrain.FuelSystem.Level",
        "fuel_consumption": "Vehicle.Powertrain.FuelSystem.InstantConsumption",
        "heart_rate": "Vehicle.Occupant.Driver.HeartRate",
    }

    def __init__(self, kuksa_host: str = "localhost", kuksa_port: int = 55556):
        self.kuksa_host = kuksa_host
        self.kuksa_port = kuksa_port
        self._client: Any = None

    async def _get_value(self, vss_path: str) -> Optional[Any]:
        """Read a single VSS value from Kuksa. Returns None on failure."""
        try:
            if self._client is None:
                from kuksa_client.grpc import VSSClient  # type: ignore[import-untyped]
                self._client = VSSClient(self.kuksa_host, self.kuksa_port)
                self._client.connect()

            result = self._client.get_current_values([vss_path])
            if result and vss_path in result:
                datapoint = result[vss_path]
                return datapoint.value if datapoint else None
            return None
        except Exception:
            return None

    async def read_gps(self) -> tuple[Optional[float], Optional[float]]:
        """Read current GPS position.

        Returns:
            Tuple of (latitude, longitude), either may be None on failure.
        """
        lat = await self._get_value(self.VSS_PATHS["latitude"])
        lon = await self._get_value(self.VSS_PATHS["longitude"])
        return (lat, lon)

    async def read_fuel_level(self) -> Optional[float]:
        """Read current fuel level percentage (0-100)."""
        return await self._get_value(self.VSS_PATHS["fuel_level"])

    async def read_fuel_consumption(self) -> Optional[float]:
        """Read current fuel consumption rate (liters per 100km)."""
        return await self._get_value(self.VSS_PATHS["fuel_consumption"])

    async def read_heart_rate(self) -> Optional[int]:
        """Read driver heart rate (BPM)."""
        value = await self._get_value(self.VSS_PATHS["heart_rate"])
        return int(value) if value is not None else None

    async def read_all(self) -> VehicleTelemetry:
        """Read all telemetry values in one call.

        Returns:
            VehicleTelemetry with all available readings (None for failures).
        """
        lat, lon = await self.read_gps()
        fuel_level = await self.read_fuel_level()
        fuel_consumption = await self.read_fuel_consumption()
        heart_rate = await self.read_heart_rate()

        return VehicleTelemetry(
            latitude=lat,
            longitude=lon,
            fuel_level=fuel_level,
            fuel_consumption=fuel_consumption,
            heart_rate=heart_rate,
        )
