"""Local Whisper-based speech-to-text using faster-whisper.

Provides low-latency on-device transcription with confidence scoring.
When confidence is below threshold, the pipeline triggers cloud fallback.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel


@dataclass
class TranscriptionResult:
    """Result from speech-to-text transcription."""

    text: str
    confidence: float  # 0.0 to 1.0
    source: str  # "local" or "cloud"


class LocalSTT:
    """Local Whisper-based speech-to-text using faster-whisper.

    Args:
        model_size: Whisper model size (e.g., "base", "small", "large-v3").
        confidence_threshold: Minimum confidence to accept local result.
    """

    def __init__(self, model_size: str = "base", confidence_threshold: float = 0.7):
        self.model = WhisperModel(model_size, compute_type="int8")
        self.confidence_threshold = confidence_threshold

    def transcribe(self, audio_samples: np.ndarray) -> TranscriptionResult:
        """Transcribe audio using local Whisper model.

        Args:
            audio_samples: Audio samples as numpy array (float32, 16kHz mono).

        Returns:
            TranscriptionResult with text, confidence score, and source label.
        """
        segments, _info = self.model.transcribe(audio_samples, beam_size=5)
        text_parts: list[str] = []
        total_logprob = 0.0
        count = 0

        for segment in segments:
            text_parts.append(segment.text)
            total_logprob += segment.avg_logprob
            count += 1

        avg_logprob = total_logprob / max(count, 1)
        confidence = self._logprob_to_confidence(avg_logprob)

        return TranscriptionResult(
            text=" ".join(text_parts).strip(),
            confidence=confidence,
            source="local",
        )

    def is_below_threshold(self, result: TranscriptionResult) -> bool:
        """Check if transcription confidence is below the threshold."""
        return result.confidence < self.confidence_threshold

    @staticmethod
    def _logprob_to_confidence(logprob: float) -> float:
        """Convert average log probability to 0-1 confidence score."""
        return min(1.0, max(0.0, math.exp(logprob)))
