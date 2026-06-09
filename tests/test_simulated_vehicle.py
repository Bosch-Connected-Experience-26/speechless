"""Tests for the SimulatedVehicleControl."""

import pytest
from hypothesis import given, strategies as st

from speechless.edge.intent_parser import Action, VehicleIntent, VehicleSystem
from speechless.edge.simulated_vehicle import SimulatedVehicleControl, VehicleState


class TestSimulatedVehicleControl:
    """Unit tests for SimulatedVehicleControl."""

    def test_initial_state(self) -> None:
        """Vehicle starts with sensible defaults."""
        vehicle = SimulatedVehicleControl()
        state = vehicle.state
        assert state.speed == 0.0
        assert state.steering_angle == 0.0
        assert state.temperature == 22.0
        assert state.doors_locked is True
        assert state.window_position == 0
        assert state.hazard_lights is False
        assert state.commands_executed == 0

    def test_hvac_set_temperature(self) -> None:
        """HVAC command updates temperature."""
        vehicle = SimulatedVehicleControl()
        intent = VehicleIntent(
            system=VehicleSystem.HVAC,
            action=Action.SET_TEMPERATURE,
            parameters={"temperature": 25},
        )
        result = vehicle.execute(intent)
        assert result["success"] is True
        assert vehicle.state.temperature == 25.0
        assert vehicle.state.commands_executed == 1

    def test_hvac_clamps_temperature(self) -> None:
        """Temperature is clamped to valid range (16-30)."""
        vehicle = SimulatedVehicleControl()
        intent = VehicleIntent(
            system=VehicleSystem.HVAC,
            action=Action.SET_TEMPERATURE,
            parameters={"temperature": 50},
        )
        vehicle.execute(intent)
        assert vehicle.state.temperature == 30.0

        intent.parameters = {"temperature": 5}
        vehicle.execute(intent)
        assert vehicle.state.temperature == 16.0

    def test_window_open_close(self) -> None:
        """Window commands update position."""
        vehicle = SimulatedVehicleControl()

        open_intent = VehicleIntent(system=VehicleSystem.WINDOWS, action=Action.OPEN)
        vehicle.execute(open_intent)
        assert vehicle.state.window_position == 100

        close_intent = VehicleIntent(system=VehicleSystem.WINDOWS, action=Action.CLOSE)
        vehicle.execute(close_intent)
        assert vehicle.state.window_position == 0

    def test_door_lock_unlock(self) -> None:
        """Door lock/unlock commands update state."""
        vehicle = SimulatedVehicleControl()
        assert vehicle.state.doors_locked is True

        unlock = VehicleIntent(system=VehicleSystem.DOORS, action=Action.UNLOCK)
        vehicle.execute(unlock)
        assert vehicle.state.doors_locked is False

        lock = VehicleIntent(system=VehicleSystem.DOORS, action=Action.LOCK)
        vehicle.execute(lock)
        assert vehicle.state.doors_locked is True

    def test_lights_on_off(self) -> None:
        """Lights commands toggle headlights."""
        vehicle = SimulatedVehicleControl()

        on = VehicleIntent(system=VehicleSystem.LIGHTS, action=Action.TURN_ON)
        vehicle.execute(on)
        assert vehicle.state.headlights is True

        off = VehicleIntent(system=VehicleSystem.LIGHTS, action=Action.TURN_OFF)
        vehicle.execute(off)
        assert vehicle.state.headlights is False

    def test_set_speed(self) -> None:
        """Speed is set and clamped to 0-200."""
        vehicle = SimulatedVehicleControl()
        vehicle.set_speed(80)
        assert vehicle.state.speed == 80.0
        assert vehicle.current_speed == 80.0

        vehicle.set_speed(250)
        assert vehicle.state.speed == 200.0

        vehicle.set_speed(-10)
        assert vehicle.state.speed == 0.0

    def test_set_steering(self) -> None:
        """Steering is set and clamped to -90..+90."""
        vehicle = SimulatedVehicleControl()
        vehicle.set_steering(30)
        assert vehicle.state.steering_angle == 30.0

        vehicle.set_steering(-100)
        assert vehicle.state.steering_angle == -90.0

        vehicle.set_steering(100)
        assert vehicle.state.steering_angle == 90.0

    def test_emergency_stop(self) -> None:
        """Emergency stop sets speed=0 and hazards=on."""
        vehicle = SimulatedVehicleControl()
        vehicle.set_speed(120)
        result = vehicle.emergency_stop()
        assert result["success"] is True
        assert vehicle.state.speed == 0.0
        assert vehicle.state.hazard_lights is True

    def test_get_state_serializable(self) -> None:
        """get_state() returns a plain dict suitable for JSON."""
        vehicle = SimulatedVehicleControl()
        vehicle.set_speed(60)
        state = vehicle.get_state()
        assert isinstance(state, dict)
        assert state["speed"] == 60.0
        assert "commands_executed" in state

    def test_commands_executed_increments(self) -> None:
        """Every action increments the command counter."""
        vehicle = SimulatedVehicleControl()
        vehicle.set_speed(50)
        vehicle.set_steering(10)
        intent = VehicleIntent(system=VehicleSystem.LIGHTS, action=Action.TURN_ON)
        vehicle.execute(intent)
        assert vehicle.state.commands_executed == 3


class TestSimulatedVehicleProperties:
    """Property-based tests for SimulatedVehicleControl."""

    @given(temp=st.integers(min_value=-50, max_value=100))
    def test_temperature_always_in_range(self, temp: int) -> None:
        """For any temperature input, result is always 16-30."""
        vehicle = SimulatedVehicleControl()
        intent = VehicleIntent(
            system=VehicleSystem.HVAC,
            action=Action.SET_TEMPERATURE,
            parameters={"temperature": temp},
        )
        vehicle.execute(intent)
        assert 16.0 <= vehicle.state.temperature <= 30.0

    @given(speed=st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False))
    def test_speed_always_in_range(self, speed: float) -> None:
        """For any speed input, result is always 0-200."""
        vehicle = SimulatedVehicleControl()
        vehicle.set_speed(speed)
        assert 0.0 <= vehicle.state.speed <= 200.0

    @given(angle=st.floats(min_value=-500, max_value=500, allow_nan=False, allow_infinity=False))
    def test_steering_always_in_range(self, angle: float) -> None:
        """For any steering input, result is always -90..+90."""
        vehicle = SimulatedVehicleControl()
        vehicle.set_steering(angle)
        assert -90.0 <= vehicle.state.steering_angle <= 90.0

    @given(
        system=st.sampled_from(VehicleSystem),
        action=st.sampled_from(Action),
    )
    def test_execute_never_crashes(self, system: VehicleSystem, action: Action) -> None:
        """Executing any system/action combination never raises."""
        vehicle = SimulatedVehicleControl()
        intent = VehicleIntent(system=system, action=action, parameters={"temperature": 22})
        result = vehicle.execute(intent)
        assert isinstance(result, dict)
        assert "success" in result
        assert "message" in result
