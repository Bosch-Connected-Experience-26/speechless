"""Intent parser for vehicle control commands.

Parses natural language vehicle commands into structured VehicleIntent
objects containing the target system, action, and parameters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class VehicleSystem(Enum):
    """Supported vehicle systems for control."""

    HVAC = "hvac"
    WINDOWS = "windows"
    DOORS = "doors"
    LIGHTS = "lights"


class Action(Enum):
    """Supported actions for vehicle systems."""

    SET_TEMPERATURE = "set_temperature"
    OPEN = "open"
    CLOSE = "close"
    LOCK = "lock"
    UNLOCK = "unlock"
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"


@dataclass
class VehicleIntent:
    """Parsed vehicle control intent."""

    system: VehicleSystem
    action: Action
    parameters: dict = field(default_factory=dict)


class IntentParser:
    """Parses natural language vehicle commands into structured intents.

    Uses keyword-based heuristic matching for deterministic, low-latency
    intent extraction. No LLM call — designed for sub-50ms execution.
    """

    def parse(self, text: str) -> Optional[VehicleIntent]:
        """Parse command text into a VehicleIntent.

        Args:
            text: Transcribed vehicle control command text.

        Returns:
            VehicleIntent if a valid intent is recognized, None otherwise.
        """
        if not text or not text.strip():
            return None

        text_lower = text.lower().strip()

        # Check systems in priority order
        if any(kw in text_lower for kw in ("temperature", "heat", "cool", "ac", "hvac", "warm", "cold")):
            return self._parse_hvac(text_lower)
        if "window" in text_lower:
            return self._parse_window(text_lower)
        if any(kw in text_lower for kw in ("door", "lock", "unlock")):
            return self._parse_door(text_lower)
        if "light" in text_lower:
            return self._parse_light(text_lower)

        return None

    def _parse_hvac(self, text: str) -> VehicleIntent:
        """Parse HVAC-related command."""
        temp_match = re.search(r"(\d+)", text)
        temp = int(temp_match.group(1)) if temp_match else 22
        return VehicleIntent(
            system=VehicleSystem.HVAC,
            action=Action.SET_TEMPERATURE,
            parameters={"temperature": temp},
        )

    def _parse_window(self, text: str) -> VehicleIntent:
        """Parse window-related command."""
        action = Action.CLOSE if "close" in text else Action.OPEN
        return VehicleIntent(system=VehicleSystem.WINDOWS, action=action, parameters={})

    def _parse_door(self, text: str) -> VehicleIntent:
        """Parse door/lock-related command."""
        action = Action.UNLOCK if "unlock" in text else Action.LOCK
        return VehicleIntent(system=VehicleSystem.DOORS, action=action, parameters={})

    def _parse_light(self, text: str) -> VehicleIntent:
        """Parse light-related command."""
        action = Action.TURN_OFF if "off" in text else Action.TURN_ON
        return VehicleIntent(system=VehicleSystem.LIGHTS, action=action, parameters={})
