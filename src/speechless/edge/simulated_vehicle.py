"""Simulated vehicle control for demo and testing.

Provides an in-memory vehicle state machine that responds to VehicleIntent
commands without requiring a running Kuksa databroker. Used by the visual
dashboard and scripted demo scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from speechless.edge.intent_parser import Action, VehicleIntent, VehicleSystem


@dataclass
class VehicleState:
    """Current state of the simulated vehicle."""

    speed: float = 0.0
    steering_angle: float = 0.0
    temperature: float = 22.0
    volume: int = 50
    hazard_lights: bool = False
    headlights: bool = False
    window_position: int = 0  # 0=closed, 100=open
    doors_locked: bool = True
    commands_executed: int = 0


class SimulatedVehicleControl:
    """In-memory vehicle simulator for demo and testing.

    Accepts VehicleIntent objects and updates internal state accordingly.
    Provides get_state() for dashboard polling and supports additional
    demo-specific commands (speed, steering) beyond the standard intents.

    Example:
        vehicle = SimulatedVehicleControl()
        intent = VehicleIntent(system=VehicleSystem.HVAC, action=Action.SET_TEMPERATURE, parameters={"temperature": 24})
        result = vehicle.execute(intent)
        assert vehicle.state.temperature == 24.0
    """

    def __init__(self) -> None:
        self._state = VehicleState()

    @property
    def state(self) -> VehicleState:
        """Current vehicle state."""
        return self._state

    @property
    def current_speed(self) -> float:
        """Current speed in km/h."""
        return self._state.speed

    @property
    def steering_angle(self) -> float:
        """Current steering angle in degrees."""
        return self._state.steering_angle

    @property
    def temperature(self) -> float:
        """Current cabin temperature in Celsius."""
        return self._state.temperature

    def execute(self, intent: VehicleIntent) -> dict:
        """Execute a vehicle intent against simulated state.

        Args:
            intent: Parsed vehicle control intent.

        Returns:
            Dict with 'success', 'message', and optionally 'previous_value'.
        """
        self._state.commands_executed += 1

        handlers = {
            VehicleSystem.HVAC: self._handle_hvac,
            VehicleSystem.WINDOWS: self._handle_windows,
            VehicleSystem.DOORS: self._handle_doors,
            VehicleSystem.LIGHTS: self._handle_lights,
        }

        handler = handlers.get(intent.system)
        if handler is None:
            return {"success": False, "message": f"Unknown system: {intent.system.value}"}

        return handler(intent)

    def set_speed(self, speed_kmh: float) -> dict:
        """Set vehicle speed (demo-specific, not from VehicleIntent).

        Args:
            speed_kmh: Target speed in km/h.

        Returns:
            Result dict.
        """
        previous = self._state.speed
        self._state.speed = max(0.0, min(200.0, speed_kmh))
        self._state.commands_executed += 1
        return {
            "success": True,
            "message": f"Speed set to {self._state.speed:.1f} km/h",
            "previous_value": previous,
        }

    def set_steering(self, angle_degrees: float) -> dict:
        """Set steering angle (demo-specific).

        Args:
            angle_degrees: Steering angle (-90 to +90 degrees).

        Returns:
            Result dict.
        """
        previous = self._state.steering_angle
        self._state.steering_angle = max(-90.0, min(90.0, angle_degrees))
        self._state.commands_executed += 1
        return {
            "success": True,
            "message": f"Steering set to {self._state.steering_angle:.1f}°",
            "previous_value": previous,
        }

    def emergency_stop(self) -> dict:
        """Emergency brake — set speed to 0 and activate hazard lights."""
        previous_speed = self._state.speed
        self._state.speed = 0.0
        self._state.hazard_lights = True
        self._state.commands_executed += 1
        return {
            "success": True,
            "message": "Emergency stop activated. Hazard lights ON.",
            "previous_value": previous_speed,
        }

    def toggle_hazard_lights(self, on: bool) -> dict:
        """Toggle hazard lights."""
        self._state.hazard_lights = on
        self._state.commands_executed += 1
        state_str = "ON" if on else "OFF"
        return {"success": True, "message": f"Hazard lights {state_str}"}

    def get_state(self) -> dict:
        """Return current vehicle state as a serializable dict for dashboard."""
        return {
            "speed": self._state.speed,
            "steering_angle": self._state.steering_angle,
            "temperature": self._state.temperature,
            "volume": self._state.volume,
            "hazard_lights": self._state.hazard_lights,
            "headlights": self._state.headlights,
            "window_position": self._state.window_position,
            "doors_locked": self._state.doors_locked,
            "commands_executed": self._state.commands_executed,
        }

    def _handle_hvac(self, intent: VehicleIntent) -> dict:
        """Handle HVAC commands."""
        temp = intent.parameters.get("temperature", 22)
        previous = self._state.temperature
        self._state.temperature = float(max(16, min(30, temp)))
        return {
            "success": True,
            "message": f"Temperature set to {self._state.temperature:.0f}°C",
            "previous_value": previous,
        }

    def _handle_windows(self, intent: VehicleIntent) -> dict:
        """Handle window commands."""
        previous = self._state.window_position
        if intent.action == Action.OPEN:
            self._state.window_position = 100
            return {"success": True, "message": "Window opened", "previous_value": previous}
        else:
            self._state.window_position = 0
            return {"success": True, "message": "Window closed", "previous_value": previous}

    def _handle_doors(self, intent: VehicleIntent) -> dict:
        """Handle door lock/unlock commands."""
        previous = self._state.doors_locked
        if intent.action == Action.UNLOCK:
            self._state.doors_locked = False
            return {"success": True, "message": "Doors unlocked", "previous_value": previous}
        else:
            self._state.doors_locked = True
            return {"success": True, "message": "Doors locked", "previous_value": previous}

    def _handle_lights(self, intent: VehicleIntent) -> dict:
        """Handle lights commands."""
        previous = self._state.headlights
        if intent.action == Action.TURN_ON:
            self._state.headlights = True
            return {"success": True, "message": "Lights turned on", "previous_value": previous}
        else:
            self._state.headlights = False
            return {"success": True, "message": "Lights turned off", "previous_value": previous}
