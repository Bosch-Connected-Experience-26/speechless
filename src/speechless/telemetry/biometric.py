"""Biometric monitoring for emergency response.

Monitors driver heart rate via Kuksa VSS and triggers emergency
routing when critical thresholds are exceeded. Supports cancellation
if heart rate normalizes within 30 seconds.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class BiometricConfig:
    """Configuration for biometric monitoring.

    Args:
        critical_threshold: Heart rate (BPM) that triggers emergency.
        sampling_interval: Seconds between heart rate readings.
        cancellation_window: Seconds to wait for normalization before confirming emergency.
    """

    critical_threshold: int = 180
    sampling_interval: float = 5.0
    cancellation_window: float = 30.0


class BiometricMonitor:
    """Monitors driver heart rate and triggers emergency routing.

    Reads heart rate from the telemetry reader at configured intervals.
    When HR exceeds critical threshold, fires an emergency callback.
    If HR normalizes within the cancellation window, cancels the emergency.

    Args:
        config: BiometricConfig with thresholds and timing.
        read_heart_rate: Async callable that returns current HR or None.
        on_emergency: Callback fired when emergency is triggered.
        on_emergency_cancelled: Callback fired when emergency is cancelled.
    """

    def __init__(
        self,
        config: Optional[BiometricConfig] = None,
        read_heart_rate: Optional[Callable[[], "asyncio.coroutines"]] = None,
        on_emergency: Optional[Callable[[], None]] = None,
        on_emergency_cancelled: Optional[Callable[[], None]] = None,
    ):
        self.config = config or BiometricConfig()
        self._read_heart_rate = read_heart_rate
        self.on_emergency = on_emergency
        self.on_emergency_cancelled = on_emergency_cancelled
        self._running = False
        self._in_emergency = False
        self._emergency_start_time: Optional[float] = None
        self._task: Optional[asyncio.Task] = None

    @property
    def in_emergency(self) -> bool:
        """Whether currently in emergency state."""
        return self._in_emergency

    def is_critical(self, heart_rate: int) -> bool:
        """Check if heart rate exceeds the critical threshold.

        Args:
            heart_rate: Current heart rate in BPM.

        Returns:
            True if HR >= critical_threshold.
        """
        return heart_rate >= self.config.critical_threshold

    async def run(self) -> None:
        """Run the biometric monitoring loop.

        Samples heart rate at configured interval. Triggers emergency
        on critical HR, cancels if normalized within cancellation window.
        """
        self._running = True
        while self._running:
            if self._read_heart_rate:
                hr = await self._read_heart_rate()
                if hr is not None:
                    self._process_heart_rate(hr)

            await asyncio.sleep(self.config.sampling_interval)

    def _process_heart_rate(self, hr: int) -> None:
        """Process a heart rate reading and manage emergency state."""
        if self.is_critical(hr):
            if not self._in_emergency:
                # Trigger emergency
                self._in_emergency = True
                self._emergency_start_time = time.monotonic()
                if self.on_emergency:
                    self.on_emergency()
        else:
            if self._in_emergency:
                # Check if within cancellation window
                elapsed = time.monotonic() - (self._emergency_start_time or 0)
                if elapsed <= self.config.cancellation_window:
                    # Cancel emergency — HR normalized in time
                    self._in_emergency = False
                    self._emergency_start_time = None
                    if self.on_emergency_cancelled:
                        self.on_emergency_cancelled()

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False

    async def start(self) -> None:
        """Start the monitoring loop as a background task."""
        self._task = asyncio.create_task(self.run())

    async def shutdown(self) -> None:
        """Stop and await the background monitoring task."""
        self.stop()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
