"""Connectivity monitor with periodic ping and mode switching.

Detects network connectivity state (ONLINE/OFFLINE) by periodically
pinging a configurable URL. Fires callbacks on state transitions
to enable the pipeline orchestrator to switch processing modes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import httpx


class ConnectivityState(Enum):
    """Network connectivity state."""

    ONLINE = "online"
    OFFLINE = "offline"


@dataclass
class ConnectivityConfig:
    """Configuration for connectivity monitoring.

    Args:
        ping_url: URL to ping for connectivity checks.
        ping_interval: Seconds between connectivity checks.
        timeout: Seconds to wait for ping response.
    """

    ping_url: str = "http://connectivitycheck.gstatic.com/generate_204"
    ping_interval: float = 3.0
    timeout: float = 3.0


class ConnectivityMonitor:
    """Monitors network connectivity and fires callbacks on state changes.

    Uses httpx for periodic HTTP pings to detect online/offline transitions.
    Designed to detect state changes within 5 seconds of actual transition.

    Args:
        config: ConnectivityConfig with ping URL and intervals.
        on_state_change: Optional callback fired on ONLINE↔OFFLINE transitions.
    """

    def __init__(
        self,
        config: Optional[ConnectivityConfig] = None,
        on_state_change: Optional[Callable[[ConnectivityState], None]] = None,
    ):
        self.config = config or ConnectivityConfig()
        self.on_state_change = on_state_change
        self._state = ConnectivityState.ONLINE
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def state(self) -> ConnectivityState:
        """Current connectivity state."""
        return self._state

    @property
    def is_online(self) -> bool:
        """Whether currently online."""
        return self._state == ConnectivityState.ONLINE

    async def check_connectivity(self) -> ConnectivityState:
        """Perform a single connectivity check.

        Returns:
            ConnectivityState.ONLINE if ping succeeds, OFFLINE otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.get(self.config.ping_url)
                if response.status_code < 400:
                    return ConnectivityState.ONLINE
                return ConnectivityState.OFFLINE
        except Exception:
            return ConnectivityState.OFFLINE

    async def run(self) -> None:
        """Run the connectivity monitoring loop.

        Checks connectivity at the configured interval and fires
        on_state_change callback when transitions occur.
        """
        self._running = True
        while self._running:
            new_state = await self.check_connectivity()
            if new_state != self._state:
                old_state = self._state
                self._state = new_state
                if self.on_state_change:
                    self.on_state_change(new_state)
            await asyncio.sleep(self.config.ping_interval)

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
