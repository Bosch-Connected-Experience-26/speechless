"""Property-based tests for the Biometric Monitor.

Property 21: Biometric emergency threshold detection — emergency triggered
iff HR >= critical_threshold.

Property 22: Emergency cancellation within time window — cancellation if
HR drops below threshold within 30s.
"""

import time

from hypothesis import given, settings
from hypothesis import strategies as st

from speechless.telemetry.biometric import BiometricConfig, BiometricMonitor


class TestBiometricEmergencyThreshold:
    """Property 21: Emergency triggered iff HR >= critical_threshold."""

    @given(
        heart_rate=st.integers(min_value=0, max_value=300),
        threshold=st.integers(min_value=100, max_value=250),
    )
    @settings(max_examples=200)
    def test_is_critical_iff_above_threshold(self, heart_rate: int, threshold: int):
        """is_critical returns True iff HR >= threshold."""
        config = BiometricConfig(critical_threshold=threshold)
        monitor = BiometricMonitor(config=config)

        result = monitor.is_critical(heart_rate)

        if heart_rate >= threshold:
            assert result is True
        else:
            assert result is False

    @given(heart_rate=st.integers(min_value=180, max_value=300))
    @settings(max_examples=100)
    def test_critical_hr_triggers_emergency(self, heart_rate: int):
        """HR at or above default threshold (180) is always critical."""
        monitor = BiometricMonitor()
        assert monitor.is_critical(heart_rate) is True

    @given(heart_rate=st.integers(min_value=0, max_value=179))
    @settings(max_examples=100)
    def test_normal_hr_not_critical(self, heart_rate: int):
        """HR below default threshold (180) is never critical."""
        monitor = BiometricMonitor()
        assert monitor.is_critical(heart_rate) is False


class TestEmergencyCancellation:
    """Property 22: Emergency cancellation within time window."""

    def test_emergency_triggered_on_critical_hr(self):
        """Emergency state activates when critical HR detected."""
        triggered = []
        config = BiometricConfig(critical_threshold=180)
        monitor = BiometricMonitor(
            config=config,
            on_emergency=lambda: triggered.append(True),
        )

        # Simulate processing a critical heart rate
        monitor._process_heart_rate(185)
        assert monitor.in_emergency is True
        assert len(triggered) == 1

    def test_emergency_cancelled_when_hr_normalizes_within_window(self):
        """Emergency cancelled if HR drops below threshold within 30s."""
        cancelled = []
        config = BiometricConfig(critical_threshold=180, cancellation_window=30.0)
        monitor = BiometricMonitor(
            config=config,
            on_emergency=lambda: None,
            on_emergency_cancelled=lambda: cancelled.append(True),
        )

        # Trigger emergency
        monitor._process_heart_rate(190)
        assert monitor.in_emergency is True

        # Normalize within cancellation window
        monitor._process_heart_rate(120)
        assert monitor.in_emergency is False
        assert len(cancelled) == 1

    def test_emergency_not_cancelled_after_window(self):
        """Emergency NOT cancelled if HR normalizes after 30s window."""
        cancelled = []
        config = BiometricConfig(critical_threshold=180, cancellation_window=0.0)  # 0s window
        monitor = BiometricMonitor(
            config=config,
            on_emergency=lambda: None,
            on_emergency_cancelled=lambda: cancelled.append(True),
        )

        # Trigger emergency
        monitor._process_heart_rate(190)
        assert monitor.in_emergency is True

        # Try to normalize — but window has passed (0s window)
        # We need the time check to fail, so set emergency_start_time to past
        monitor._emergency_start_time = time.monotonic() - 31.0  # 31s ago
        monitor._process_heart_rate(120)

        # Should NOT be cancelled (beyond window)
        assert monitor.in_emergency is True
        assert len(cancelled) == 0

    @given(threshold=st.integers(min_value=100, max_value=250))
    @settings(max_examples=50)
    def test_no_emergency_below_threshold(self, threshold: int):
        """No emergency triggered for HR below threshold."""
        config = BiometricConfig(critical_threshold=threshold)
        monitor = BiometricMonitor(config=config)

        monitor._process_heart_rate(threshold - 1)
        assert monitor.in_emergency is False

    def test_repeated_critical_hr_doesnt_retrigger(self):
        """Multiple critical readings don't retrigger (already in emergency)."""
        triggered = []
        config = BiometricConfig(critical_threshold=180)
        monitor = BiometricMonitor(
            config=config,
            on_emergency=lambda: triggered.append(True),
        )

        monitor._process_heart_rate(185)
        monitor._process_heart_rate(190)
        monitor._process_heart_rate(200)

        # Only triggered once
        assert len(triggered) == 1
        assert monitor.in_emergency is True
