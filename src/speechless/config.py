"""Configuration loading for the Speechless voice assistant.

Loads configuration from environment variables with sensible defaults.
Environment variable names use the SPEECHLESS_ prefix and uppercase field names.
"""

from __future__ import annotations

import os

from speechless.models import AppConfig


def load_config() -> AppConfig:
    """Load application configuration from environment variables.

    Environment variables are mapped as follows:
        SPEECHLESS_EDGE_TARGET        -> edge_target (default: "lmstudio")
        SPEECHLESS_LMSTUDIO_URL       -> lmstudio_url (default: "http://localhost:1234/v1")
        SPEECHLESS_JETSON_URL         -> jetson_url (default: "http://jetson-device:8080/v1")
        SPEECHLESS_EDGE_MODEL_NAME    -> edge_model_name (default: "local-model")
        SPEECHLESS_BEDROCK_PROFILE    -> bedrock_profile (default: "losrudos")
        SPEECHLESS_BEDROCK_MODEL_ID   -> bedrock_model_id (default: "anthropic.claude-3-haiku-20240307-v1:0")
        SPEECHLESS_BEDROCK_REGION     -> bedrock_region (default: "us-east-1")
        SPEECHLESS_PING_URL           -> ping_url (default: "http://connectivitycheck.gstatic.com/generate_204")
        SPEECHLESS_PING_INTERVAL      -> ping_interval_seconds (default: 3.0)
        SPEECHLESS_KUKSA_HOST         -> kuksa_host (default: "localhost")
        SPEECHLESS_KUKSA_PORT         -> kuksa_port (default: 55555)
        SPEECHLESS_CRITICAL_HR_THRESHOLD -> critical_hr_threshold (default: 180)
        SPEECHLESS_HR_SAMPLING_INTERVAL  -> hr_sampling_interval (default: 5.0)
        SPEECHLESS_WHISPER_MODEL_SIZE    -> whisper_model_size (default: "base")
        SPEECHLESS_STT_CONFIDENCE_THRESHOLD -> stt_confidence_threshold (default: 0.7)
        SPEECHLESS_CLASSIFICATION_THRESHOLD -> classification_confidence_threshold (default: 0.6)

    Returns:
        AppConfig with values from environment or defaults.
    """
    return AppConfig(
        # Edge LLM
        edge_target=os.environ.get("SPEECHLESS_EDGE_TARGET", "lmstudio"),
        lmstudio_url=os.environ.get("SPEECHLESS_LMSTUDIO_URL", "http://localhost:1234/v1"),
        jetson_url=os.environ.get("SPEECHLESS_JETSON_URL", "http://jetson-device:8080/v1"),
        edge_model_name=os.environ.get("SPEECHLESS_EDGE_MODEL_NAME", "local-model"),
        # AWS Bedrock
        bedrock_profile=os.environ.get("SPEECHLESS_BEDROCK_PROFILE", "losrudos"),
        bedrock_model_id=os.environ.get(
            "SPEECHLESS_BEDROCK_MODEL_ID",
            "anthropic.claude-3-haiku-20240307-v1:0",
        ),
        bedrock_region=os.environ.get("SPEECHLESS_BEDROCK_REGION", "us-east-1"),
        # Connectivity
        ping_url=os.environ.get(
            "SPEECHLESS_PING_URL",
            "http://connectivitycheck.gstatic.com/generate_204",
        ),
        ping_interval_seconds=float(
            os.environ.get("SPEECHLESS_PING_INTERVAL", "3.0")
        ),
        # Kuksa
        kuksa_host=os.environ.get("SPEECHLESS_KUKSA_HOST", "localhost"),
        kuksa_port=int(os.environ.get("SPEECHLESS_KUKSA_PORT", "55555")),
        # Biometric
        critical_hr_threshold=int(
            os.environ.get("SPEECHLESS_CRITICAL_HR_THRESHOLD", "180")
        ),
        hr_sampling_interval=float(
            os.environ.get("SPEECHLESS_HR_SAMPLING_INTERVAL", "5.0")
        ),
        # STT
        whisper_model_size=os.environ.get("SPEECHLESS_WHISPER_MODEL_SIZE", "base"),
        stt_confidence_threshold=float(
            os.environ.get("SPEECHLESS_STT_CONFIDENCE_THRESHOLD", "0.7")
        ),
        # Classification
        classification_confidence_threshold=float(
            os.environ.get("SPEECHLESS_CLASSIFICATION_THRESHOLD", "0.6")
        ),
    )
