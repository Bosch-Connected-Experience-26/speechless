"""Data models for the Speechless voice assistant pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PipelineState(Enum):
    """State of the voice assistant pipeline."""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    CLASSIFYING = "classifying"
    EXECUTING = "executing"
    RESPONDING = "responding"
    ERROR = "error"


class ProcessingMode(Enum):
    """Current processing mode based on connectivity."""

    ONLINE = "online"
    OFFLINE = "offline"


@dataclass
class PipelineContext:
    """Context passed through the processing pipeline.

    Tracks the current state, connectivity mode, and accumulated results
    as a voice command flows through the pipeline stages.
    """

    state: PipelineState = PipelineState.IDLE
    mode: ProcessingMode = ProcessingMode.ONLINE
    transcription: Optional[str] = None
    confidence: float = 0.0
    classification: Optional[str] = None
    routing: Optional[str] = None
    response_text: Optional[str] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AppConfig:
    """Top-level application configuration.

    All fields have sensible defaults and can be overridden via environment
    variables using the load_config() function in speechless.config.
    """

    # Edge LLM
    edge_target: str = "lmstudio"  # "lmstudio" or "jetson"
    lmstudio_url: str = "http://localhost:1234/v1"
    jetson_url: str = "http://jetson-device:8080/v1"
    edge_model_name: str = "local-model"

    # AWS Bedrock
    bedrock_profile: str = "losrudos"
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_region: str = "us-east-1"

    # Connectivity
    ping_url: str = "http://connectivitycheck.gstatic.com/generate_204"
    ping_interval_seconds: float = 3.0

    # Kuksa
    kuksa_host: str = "localhost"
    kuksa_port: int = 55555

    # Biometric
    critical_hr_threshold: int = 180
    hr_sampling_interval: float = 5.0

    # STT
    whisper_model_size: str = "base"
    stt_confidence_threshold: float = 0.7

    # Classification
    classification_confidence_threshold: float = 0.6
