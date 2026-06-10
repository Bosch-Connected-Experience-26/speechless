"""Runtime settings for the dashboard server."""

from __future__ import annotations

from dataclasses import dataclass

from speechless.models import AppConfig

VALID_DASHBOARD_MODES = {"interactive", "demo"}
VALID_BACKENDS = {"kuksa", "simulated"}
VALID_ASR_PROVIDERS = {"local_whisper", "lmstudio_whisper", "aws"}
VALID_TTS_PROVIDERS = {"local_pyttsx3", "aws"}


@dataclass(frozen=True)
class DashboardRuntime:
    """Resolved runtime choices for the dashboard application."""

    mode: str = "interactive"
    backend: str = "kuksa"
    asr_provider: str = "local_whisper"
    tts_provider: str = "local_pyttsx3"
    host: str = "0.0.0.0"
    port: int = 5001
    debug: bool = False

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        mode: str = "interactive",
        backend: str | None = None,
        asr_provider: str | None = None,
        tts_provider: str | None = None,
        host: str = "0.0.0.0",
        port: int = 5001,
        debug: bool = False,
    ) -> DashboardRuntime:
        """Create runtime settings from app config plus CLI overrides."""
        resolved = cls(
            mode=mode,
            backend=backend or config.backend,
            asr_provider=asr_provider or config.asr_provider,
            tts_provider=tts_provider or config.tts_provider,
            host=host,
            port=port,
            debug=debug,
        )
        resolved.validate()
        return resolved

    def validate(self) -> None:
        """Validate runtime settings."""
        if self.mode not in VALID_DASHBOARD_MODES:
            raise ValueError(f"Invalid dashboard mode: {self.mode}")
        if self.backend not in VALID_BACKENDS:
            raise ValueError(f"Invalid dashboard backend: {self.backend}")
        if self.asr_provider not in VALID_ASR_PROVIDERS:
            raise ValueError(f"Invalid ASR provider: {self.asr_provider}")
        if self.tts_provider not in VALID_TTS_PROVIDERS:
            raise ValueError(f"Invalid TTS provider: {self.tts_provider}")

    def to_dict(self) -> dict:
        """Return JSON-serializable runtime settings."""
        return {
            "mode": self.mode,
            "backend": self.backend,
            "asr_provider": self.asr_provider,
            "tts_provider": self.tts_provider,
            "host": self.host,
            "port": self.port,
            "debug": self.debug,
        }
