"""Property-based tests for the Vehicle Controller.

Property 5: Intent-to-VSS signal mapping correctness — signal path starts
with "Vehicle." and has ≥3 segments.

Property 6: Error messages are descriptive — contain system and action name.

Property 9: VSS path format validity — "Vehicle." prefix, ≥3 segments,
[A-Za-z0-9]+ pattern per segment.

Property 10: Exponential backoff retry timing — delay = base_delay × multiplier^N,
max 3 attempts.
"""

import asyncio
import re

from hypothesis import given, settings
from hypothesis import strategies as st

from speechless.edge.intent_parser import Action, VehicleIntent, VehicleSystem
from speechless.edge.vehicle_controller import VehicleController
from speechless.utils.retry import RetryConfig, compute_backoff_delay

# Strategy for valid VehicleIntents
valid_intents = st.sampled_from([
    VehicleIntent(system=VehicleSystem.HVAC, action=Action.SET_TEMPERATURE, parameters={"temperature": 22}),
    VehicleIntent(system=VehicleSystem.WINDOWS, action=Action.OPEN, parameters={}),
    VehicleIntent(system=VehicleSystem.WINDOWS, action=Action.CLOSE, parameters={}),
    VehicleIntent(system=VehicleSystem.DOORS, action=Action.LOCK, parameters={}),
    VehicleIntent(system=VehicleSystem.DOORS, action=Action.UNLOCK, parameters={}),
    VehicleIntent(system=VehicleSystem.LIGHTS, action=Action.TURN_ON, parameters={}),
    VehicleIntent(system=VehicleSystem.LIGHTS, action=Action.TURN_OFF, parameters={}),
])


class TestIntentToVSSSignalMapping:
    """Property 5: Intent-to-VSS signal mapping correctness."""

    @given(intent=valid_intents)
    @settings(max_examples=100)
    def test_signal_path_starts_with_vehicle(self, intent: VehicleIntent):
        """All mapped signal paths start with 'Vehicle.'."""
        controller = VehicleController()
        signal = controller.intent_to_signal(intent)
        assert signal is not None
        assert signal.path.startswith("Vehicle.")

    @given(intent=valid_intents)
    @settings(max_examples=100)
    def test_signal_path_has_three_or_more_segments(self, intent: VehicleIntent):
        """All mapped signal paths have at least 3 dot-separated segments."""
        controller = VehicleController()
        signal = controller.intent_to_signal(intent)
        assert signal is not None
        parts = signal.path.split(".")
        assert len(parts) >= 3

    @given(intent=valid_intents)
    @settings(max_examples=100)
    def test_signal_has_value(self, intent: VehicleIntent):
        """All mapped signals have a non-None value."""
        controller = VehicleController()
        signal = controller.intent_to_signal(intent)
        assert signal is not None
        assert signal.value is not None

    @given(intent=valid_intents)
    @settings(max_examples=100)
    def test_signal_has_type(self, intent: VehicleIntent):
        """All mapped signals have a valid type string."""
        controller = VehicleController()
        signal = controller.intent_to_signal(intent)
        assert signal is not None
        assert signal.type in ("int32", "uint8", "float", "boolean", "string")

    def test_actuate_wraps_values_as_kuksa_datapoints(self):
        """Kuksa writes use Datapoint wrappers required by kuksa-client."""
        captured = {}

        class FakeKuksaClient:
            def set_current_values(self, values):
                captured.update(values)

        controller = VehicleController()
        controller._connected = True
        controller._client = FakeKuksaClient()
        intent = VehicleIntent(
            system=VehicleSystem.DOORS,
            action=Action.LOCK,
            parameters={},
        )

        result = asyncio.run(controller.actuate(intent))

        assert result.success is True
        datapoint = captured["Vehicle.Cabin.Door.Row1.DriverSide.IsLocked"]
        assert datapoint.value is True


class TestErrorMessages:
    """Property 6: Error messages are descriptive."""

    @given(
        intent=valid_intents,
        error_msg=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_error_message_contains_system_name(self, intent: VehicleIntent, error_msg: str):
        """Error message always contains the system name."""
        controller = VehicleController()
        error = ValueError(error_msg)
        message = controller.generate_error_message(error, intent)
        system_name = intent.system.value.replace("_", " ")
        assert system_name in message

    @given(
        intent=valid_intents,
        error_msg=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_error_message_contains_action_name(self, intent: VehicleIntent, error_msg: str):
        """Error message always contains the action name."""
        controller = VehicleController()
        error = ValueError(error_msg)
        message = controller.generate_error_message(error, intent)
        action_name = intent.action.value.replace("_", " ")
        assert action_name in message


class TestVSSPathFormatValidity:
    """Property 9: VSS path format validity."""

    @given(intent=valid_intents)
    @settings(max_examples=100)
    def test_vss_paths_have_vehicle_prefix(self, intent: VehicleIntent):
        """All VSS paths from the controller start with 'Vehicle.'."""
        controller = VehicleController()
        signal = controller.intent_to_signal(intent)
        assert signal is not None
        assert signal.path.startswith("Vehicle.")

    @given(intent=valid_intents)
    @settings(max_examples=100)
    def test_vss_paths_have_three_plus_segments(self, intent: VehicleIntent):
        """All VSS paths have ≥3 segments."""
        controller = VehicleController()
        signal = controller.intent_to_signal(intent)
        assert signal is not None
        parts = signal.path.split(".")
        assert len(parts) >= 3

    @given(intent=valid_intents)
    @settings(max_examples=100)
    def test_vss_path_segments_are_alphanumeric(self, intent: VehicleIntent):
        """All segments in VSS paths match [A-Za-z0-9]+."""
        controller = VehicleController()
        signal = controller.intent_to_signal(intent)
        assert signal is not None
        for part in signal.path.split("."):
            assert re.match(r"^[A-Za-z0-9]+$", part), f"Invalid segment: {part}"

    def test_format_vss_path_valid(self):
        """Valid paths pass format validation."""
        path = "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature"
        assert VehicleController.format_vss_path(path) == path

    def test_format_vss_path_rejects_no_vehicle_prefix(self):
        """Paths without 'Vehicle.' prefix are rejected."""
        import pytest
        with pytest.raises(ValueError, match="must start with 'Vehicle.'"):
            VehicleController.format_vss_path("Cabin.HVAC.Temperature")

    def test_format_vss_path_rejects_too_few_segments(self):
        """Paths with fewer than 3 segments are rejected."""
        import pytest
        with pytest.raises(ValueError, match="at least 3 segments"):
            VehicleController.format_vss_path("Vehicle.X")


class TestExponentialBackoffRetryTiming:
    """Property 10: Exponential backoff retry timing."""

    @given(
        attempt=st.integers(min_value=0, max_value=2),
        base_delay=st.floats(min_value=0.1, max_value=10.0),
        multiplier=st.floats(min_value=1.0, max_value=5.0),
    )
    @settings(max_examples=200)
    def test_delay_equals_formula(self, attempt: int, base_delay: float, multiplier: float):
        """Delay = base_delay × multiplier^attempt."""
        config = RetryConfig(base_delay=base_delay, multiplier=multiplier, max_delay=1000.0)
        delay = compute_backoff_delay(attempt, config)
        expected = base_delay * (multiplier ** attempt)
        assert abs(delay - expected) < 1e-6

    @given(
        attempt=st.integers(min_value=0, max_value=10),
        base_delay=st.floats(min_value=0.1, max_value=5.0),
        multiplier=st.floats(min_value=1.0, max_value=5.0),
        max_delay=st.floats(min_value=0.5, max_value=30.0),
    )
    @settings(max_examples=200)
    def test_delay_capped_at_max(self, attempt: int, base_delay: float, multiplier: float, max_delay: float):
        """Delay never exceeds max_delay."""
        config = RetryConfig(base_delay=base_delay, multiplier=multiplier, max_delay=max_delay)
        delay = compute_backoff_delay(attempt, config)
        assert delay <= max_delay + 1e-9  # float tolerance

    def test_three_retries_max(self):
        """Default config allows exactly 3 retries (4 total attempts)."""
        config = RetryConfig()
        assert config.max_retries == 3

    @given(attempt=st.integers(min_value=0, max_value=2))
    @settings(max_examples=100)
    def test_delays_increase_monotonically(self, attempt: int):
        """Each subsequent delay is ≥ the previous (with default multiplier > 1)."""
        config = RetryConfig(base_delay=1.0, multiplier=2.0, max_delay=100.0)
        if attempt > 0:
            current = compute_backoff_delay(attempt, config)
            previous = compute_backoff_delay(attempt - 1, config)
            assert current >= previous
