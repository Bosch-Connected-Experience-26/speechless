"""Cloud STT fallback using OpenAI Whisper API.

Triggered when local STT confidence is below threshold.
If the cloud service is unavailable, returns the local result regardless.
"""

from __future__ import annotations

import io
import struct
import wave
from typing import Optional

import numpy as np
from openai import OpenAI

from speechless.speech.stt_local import TranscriptionResult


class CloudSTT:
    """Cloud-based speech-to-text fallback using OpenAI Whisper API.

    Args:
        api_key: OpenAI API key for cloud Whisper access.
        timeout: Request timeout in seconds.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: float = 5.0):
        self.client = OpenAI(api_key=api_key, timeout=timeout) if api_key else None
        self.timeout = timeout

    def transcribe(
        self, audio_samples: np.ndarray, sample_rate: int = 16000
    ) -> Optional[TranscriptionResult]:
        """Transcribe audio using cloud Whisper API.

        Args:
            audio_samples: Audio samples as numpy array (float32, 16kHz mono).
            sample_rate: Sample rate of the audio.

        Returns:
            TranscriptionResult with high confidence, or None if unavailable.
        """
        if self.client is None:
            return None

        try:
            # Convert numpy audio to WAV bytes for the API
            wav_bytes = self._numpy_to_wav(audio_samples, sample_rate)
            wav_file = io.BytesIO(wav_bytes)
            wav_file.name = "audio.wav"

            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=wav_file,
            )

            return TranscriptionResult(
                text=response.text.strip(),
                confidence=0.95,  # Cloud typically high confidence
                source="cloud",
            )
        except Exception:
            return None

    def fallback_transcribe(
        self,
        audio_samples: np.ndarray,
        local_result: TranscriptionResult,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        """Attempt cloud transcription; fall back to local result if unavailable.

        This is the main entry point for the fallback logic:
        - If cloud succeeds, return cloud result.
        - If cloud fails or is unavailable, return local result as-is.

        Args:
            audio_samples: Audio samples.
            local_result: The local STT result (used as fallback).
            sample_rate: Audio sample rate.

        Returns:
            Best available TranscriptionResult.
        """
        cloud_result = self.transcribe(audio_samples, sample_rate)
        if cloud_result is not None:
            return cloud_result
        return local_result

    @staticmethod
    def _numpy_to_wav(samples: np.ndarray, sample_rate: int) -> bytes:
        """Convert numpy float32 audio to WAV bytes."""
        # Convert float32 [-1.0, 1.0] to int16
        int16_samples = (samples * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(int16_samples.tobytes())
        return buf.getvalue()
