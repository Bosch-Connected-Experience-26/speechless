"""Configuration loading from environment variables with sensible defaults."""

import os

from speechless.models import AppConfig


def _get_env(primary: str, *fallbacks: str, default: str = "") -> str:
    """Get an environment variable, trying primary key first then fallbacks."""
    value = os.environ.get(primary)
    if value is not None:
        return value
    for fallback in fallbacks:
        value = os.environ.get(fallback)
        if value is not None:
            return value
    return default


def load_config() -> AppConfig:
    """Load application configuration from environment variables.

    Environment variables (all prefixed with SPEECHLESS_):
        SPEECHLESS_EDGE_TARGET: Edge LLM target ("lmstudio" or "jetson")
        SPEECHLESS_EDGE_LM_URL / SPEECHLESS_LMSTUDIO_URL: Edge LLM endpoint URL (LM Studio default)
        SPEECHLESS_JETSON_URL: Jetson TensorRT endpoint URL
        SPEECHLESS_EDGE_MODEL_NAME: Edge model name for API calls
        SPEECHLESS_BEDROCK_PROFILE: AWS CLI profile name for Bedrock
        SPEECHLESS_BEDROCK_MODEL_ID / SPEECHLESS_BEDROCK_MODEL: AWS Bedrock model ID
        SPEECHLESS_BEDROCK_REGION: AWS region for Bedrock
        SPEECHLESS_PING_URL: URL for connectivity checks
        SPEECHLESS_PING_INTERVAL: Connectivity ping interval in seconds
        SPEECHLESS_BACKEND: Vehicle backend ("kuksa" or "simulated")
        SPEECHLESS_KUKSA_HOST: Kuksa databroker hostname
        SPEECHLESS_KUKSA_PORT: Kuksa databroker gRPC port
        SPEECHLESS_ASR_PROVIDER: ASR provider ("local_whisper", "mlx_whisper", "lmstudio_whisper", or "aws")
        SPEECHLESS_ASR_MODEL_NAME: ASR model name for OpenAI-compatible providers
        SPEECHLESS_LMSTUDIO_ASR_URL: LM Studio Whisper-compatible endpoint URL
        SPEECHLESS_MLX_WHISPER_MODEL: MLX Whisper model repo/path
        SPEECHLESS_TTS_PROVIDER: TTS provider ("local_pyttsx3" or "aws")
        SPEECHLESS_AWS_TTS_VOICE_ID: AWS Polly voice ID
        SPEECHLESS_CRITICAL_HR_THRESHOLD: Heart rate emergency threshold (BPM)
        SPEECHLESS_HR_SAMPLING_INTERVAL: Heart rate sampling interval in seconds
        SPEECHLESS_WHISPER_MODEL_SIZE: Whisper model size for local STT
        SPEECHLESS_STT_CONFIDENCE_THRESHOLD / SPEECHLESS_CONFIDENCE_THRESHOLD: STT confidence threshold
        SPEECHLESS_CLASSIFICATION_THRESHOLD: Classification confidence threshold

    Returns:
        AppConfig with values from environment or defaults.
    """
    config = AppConfig(
        edge_target=_get_env("SPEECHLESS_EDGE_TARGET", default="lmstudio"),
        edge_lm_url=_get_env(
            "SPEECHLESS_EDGE_LM_URL",
            "SPEECHLESS_LMSTUDIO_URL",
            default="http://localhost:1234/v1",
        ),
        jetson_url=_get_env("SPEECHLESS_JETSON_URL", default="http://jetson-device:8080/v1"),
        edge_model_name=_get_env("SPEECHLESS_EDGE_MODEL_NAME", default="local-model"),
        bedrock_profile=_get_env("SPEECHLESS_BEDROCK_PROFILE", default="losrudos"),
        bedrock_model_id=_get_env(
            "SPEECHLESS_BEDROCK_MODEL_ID",
            "SPEECHLESS_BEDROCK_MODEL",
            default="anthropic.claude-3-haiku-20240307-v1:0",
        ),
        bedrock_region=_get_env("SPEECHLESS_BEDROCK_REGION", default="us-east-1"),
        ping_url=_get_env(
            "SPEECHLESS_PING_URL",
            default="http://connectivitycheck.gstatic.com/generate_204",
        ),
        ping_interval_seconds=float(
            _get_env("SPEECHLESS_PING_INTERVAL", default="3.0")
        ),
        backend=_get_env("SPEECHLESS_BACKEND", default="kuksa"),
        kuksa_host=_get_env("SPEECHLESS_KUKSA_HOST", default="localhost"),
        kuksa_port=int(_get_env("SPEECHLESS_KUKSA_PORT", default="55556")),
        asr_provider=_get_env("SPEECHLESS_ASR_PROVIDER", default="local_whisper"),
        asr_model_name=_get_env("SPEECHLESS_ASR_MODEL_NAME", default="whisper-1"),
        lmstudio_asr_url=_get_env(
            "SPEECHLESS_LMSTUDIO_ASR_URL",
            "SPEECHLESS_EDGE_LM_URL",
            "SPEECHLESS_LMSTUDIO_URL",
            default="http://localhost:1234/v1",
        ),
        mlx_whisper_model=_get_env(
            "SPEECHLESS_MLX_WHISPER_MODEL",
            default="mlx-community/whisper-base",
        ),
        tts_provider=_get_env("SPEECHLESS_TTS_PROVIDER", default="local_pyttsx3"),
        aws_tts_voice_id=_get_env("SPEECHLESS_AWS_TTS_VOICE_ID", default="Joanna"),
        critical_hr_threshold=int(
            _get_env("SPEECHLESS_CRITICAL_HR_THRESHOLD", default="180")
        ),
        hr_sampling_interval=float(
            _get_env("SPEECHLESS_HR_SAMPLING_INTERVAL", default="5.0")
        ),
        whisper_model_size=_get_env("SPEECHLESS_WHISPER_MODEL_SIZE", default="base"),
        stt_confidence_threshold=float(
            _get_env(
                "SPEECHLESS_STT_CONFIDENCE_THRESHOLD",
                "SPEECHLESS_CONFIDENCE_THRESHOLD",
                default="0.7",
            )
        ),
        classification_confidence_threshold=float(
            _get_env("SPEECHLESS_CLASSIFICATION_THRESHOLD", default="0.6")
        ),
    )
    return config
