"""Audio capture module using sounddevice.

Captures audio from the vehicle microphone at 16kHz mono for
speech-to-text processing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import sounddevice as sd


@dataclass
class AudioSegment:
    """Raw audio data from microphone capture."""

    samples: np.ndarray
    sample_rate: int
    duration_seconds: float


class AudioCapture:
    """Captures audio from the vehicle microphone using sounddevice.

    Args:
        sample_rate: Audio sample rate in Hz (default: 16000 for Whisper).
        chunk_duration: Duration of each recording in seconds.
    """

    def __init__(self, sample_rate: int = 16000, chunk_duration: float = 5.0):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration

    def record(self) -> AudioSegment:
        """Record a single audio segment from the default input device.

        Returns:
            AudioSegment with captured samples.
        """
        frames = int(self.sample_rate * self.chunk_duration)
        audio = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        return AudioSegment(
            samples=audio.flatten(),
            sample_rate=self.sample_rate,
            duration_seconds=self.chunk_duration,
        )
