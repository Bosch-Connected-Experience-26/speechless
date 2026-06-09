"""Data models for the Speechless voice assistant pipeline."""

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
class ConversationTurn:
    """A single turn in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None


@dataclass
class PipelineContext:
    """Context passed through the processing pipeline.

    Holds the current pipeline state, processing mode, and conversation context
    for multi-turn interactions (especially during offline mode).
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
    conversation_history: list[ConversationTurn] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class AppConfig:
    """Top-level application configuration."""

    # Edge LLM
    edge_target: str = "lmstudio"  # "lmstudio" or "jetson"
    edge_lm_url: str = "http://localhost:1234/v1"
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
    kuksa_port: int = 55556

    # Biometric
    critical_hr_threshold: int = 180
    hr_sampling_interval: float = 5.0

    # STT
    whisper_model_size: str = "base"
    stt_confidence_threshold: float = 0.7

    # Classification
    classification_confidence_threshold: float = 0.6
