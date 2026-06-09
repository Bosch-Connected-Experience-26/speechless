"""Response engine with text-to-speech output.

Uses pyttsx3 for offline TTS — no cloud dependency for audio output.
Provides specialized methods for confirmations, errors, and alerts.
"""

from __future__ import annotations

from typing import Optional

import pyttsx3


class ResponseEngine:
    """Text-to-speech response engine using pyttsx3.

    Provides methods for different response types: general speech,
    vehicle control confirmations, error announcements, and
    emergency alerts.
    """

    def __init__(self, rate: int = 175, volume: float = 1.0):
        """Initialize the TTS engine.

        Args:
            rate: Speech rate in words per minute.
            volume: Volume level (0.0 to 1.0).
        """
        self._engine: Optional[pyttsx3.Engine] = None
        self._rate = rate
        self._volume = volume

    def _get_engine(self) -> pyttsx3.Engine:
        """Lazy-initialize the pyttsx3 engine."""
        if self._engine is None:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            self._engine.setProperty("volume", self._volume)
        return self._engine

    def speak(self, text: str) -> None:
        """Speak text using TTS.

        Args:
            text: Text to speak aloud.
        """
        engine = self._get_engine()
        engine.say(text)
        engine.runAndWait()

    def confirm_actuation(self, system: str, action: str) -> str:
        """Generate and speak a vehicle control confirmation.

        Args:
            system: Vehicle system name (e.g., "hvac", "windows").
            action: Action performed (e.g., "set_temperature", "open").

        Returns:
            The confirmation message text.
        """
        system_display = system.replace("_", " ").title()
        action_display = action.replace("_", " ")
        message = f"{system_display}: {action_display} completed successfully."
        self.speak(message)
        return message

    def announce_error(self, error_message: str) -> str:
        """Announce an error to the driver.

        Args:
            error_message: Description of what went wrong.

        Returns:
            The announcement text.
        """
        message = f"I'm sorry, there was an issue: {error_message}"
        self.speak(message)
        return message

    def emergency_alert(self, route_info: str) -> str:
        """Announce a biometric emergency with routing information.

        Args:
            route_info: Description of the emergency route (e.g., hospital name, ETA).

        Returns:
            The emergency alert text.
        """
        message = f"Emergency detected. {route_info}"
        self.speak(message)
        return message
