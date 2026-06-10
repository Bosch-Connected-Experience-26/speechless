"""ASR and TTS provider adapters for dashboard interaction."""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from threading import Thread

import numpy as np

from speechless.models import AppConfig


@dataclass
class ASRProviderResult:
    """Result from a dashboard ASR provider."""

    text: str
    confidence: float
    source: str
    error_message: str | None = None


class DashboardASR:
    """Transcribes browser-uploaded WAV audio through a configured provider."""

    def __init__(self, config: AppConfig, provider: str | None = None) -> None:
        self.config = config
        self.provider = provider or config.asr_provider
        self._local_stt = None

    def transcribe_wav(self, wav_bytes: bytes) -> ASRProviderResult:
        """Transcribe WAV bytes and gracefully fall back when providers fail."""
        samples, _sample_rate = self._decode_wav(wav_bytes)

        if self.provider == "lmstudio_whisper":
            result = self._transcribe_lmstudio(wav_bytes)
            if result is not None:
                return result
            return self._transcribe_local(samples)

        if self.provider == "aws":
            result = self._transcribe_aws(wav_bytes)
            if result is not None:
                return result
            local = self._transcribe_local(samples)
            if local.error_message is None:
                local.source = "local_whisper_fallback"
            return local

        return self._transcribe_local(samples)

    def samples_to_wav(self, samples: np.ndarray, sample_rate: int) -> bytes:
        """Encode float32 samples as 16-bit mono PCM WAV bytes."""
        return self._samples_to_wav(samples, sample_rate)

    def _transcribe_local(self, samples: np.ndarray) -> ASRProviderResult:
        try:
            if self._local_stt is None:
                from speechless.speech.stt_local import LocalSTT

                self._local_stt = LocalSTT(
                    model_size=self.config.whisper_model_size,
                    confidence_threshold=self.config.stt_confidence_threshold,
                )
            result = self._local_stt.transcribe(samples)
            return ASRProviderResult(
                text=result.text,
                confidence=result.confidence,
                source=result.source,
            )
        except Exception as e:
            return ASRProviderResult(
                text="",
                confidence=0.0,
                source="local",
                error_message=f"Local Whisper ASR unavailable: {type(e).__name__}: {e}",
            )

    def _transcribe_lmstudio(self, wav_bytes: bytes) -> ASRProviderResult | None:
        try:
            from openai import OpenAI

            client = OpenAI(
                base_url=self.config.lmstudio_asr_url,
                api_key="not-needed",
                timeout=10.0,
            )
            wav_file = io.BytesIO(wav_bytes)
            wav_file.name = "audio.wav"
            response = client.audio.transcriptions.create(
                model=self.config.asr_model_name,
                file=wav_file,
            )
            return ASRProviderResult(
                text=response.text.strip(),
                confidence=0.95,
                source="lmstudio_whisper",
            )
        except Exception:
            return None

    def _transcribe_aws(self, wav_bytes: bytes) -> ASRProviderResult | None:
        """AWS Transcribe raw-byte support is not configured in this app yet.

        Boto3's batch Transcribe API requires an S3 media URI or a streaming
        client dependency. The dashboard keeps this provider selectable and
        falls back to local Whisper until that deployment wiring exists.
        """
        return None

    @staticmethod
    def _decode_wav(wav_bytes: bytes) -> tuple[np.ndarray, int]:
        """Decode mono/stereo PCM WAV bytes to float32 samples."""
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())

        if sample_width != 2:
            raise ValueError("Only 16-bit PCM WAV audio is supported")

        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)
        return samples, sample_rate

    @staticmethod
    def _samples_to_wav(samples: np.ndarray, sample_rate: int) -> bytes:
        clipped = np.clip(samples, -1.0, 1.0)
        int16_samples = (clipped * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(int16_samples.tobytes())
        return buf.getvalue()


class DashboardTTS:
    """Text-to-speech adapter for configured dashboard providers."""

    def __init__(self, config: AppConfig, provider: str | None = None) -> None:
        self.config = config
        self.provider = provider or config.tts_provider

    def speak_async(self, text: str) -> dict:
        """Speak text without blocking the request when possible."""
        if not text.strip():
            return {"provider": self.provider, "queued": False, "error": "empty text"}

        if self.provider == "aws":
            return self._speak_aws_async(text)
        return self._speak_local_async(text)

    def _speak_local_async(self, text: str) -> dict:
        def run() -> None:
            try:
                from speechless.response.tts import ResponseEngine

                ResponseEngine().speak(text)
            except Exception:
                pass

        Thread(target=run, daemon=True).start()
        return {"provider": "local_pyttsx3", "queued": True}

    def _speak_aws_async(self, text: str) -> dict:
        def run() -> None:
            try:
                import boto3

                session = boto3.Session(profile_name=self.config.bedrock_profile)
                client = session.client("polly", region_name=self.config.bedrock_region)
                client.synthesize_speech(
                    Text=text,
                    OutputFormat="mp3",
                    VoiceId=self.config.aws_tts_voice_id,
                )
            except Exception:
                pass

        Thread(target=run, daemon=True).start()
        return {"provider": "aws", "queued": True}
