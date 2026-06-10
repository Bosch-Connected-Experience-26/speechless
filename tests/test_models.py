"""Tests for data models and configuration."""

import os
from datetime import datetime

from speechless.config import load_config
from speechless.models import (
    AppConfig,
    ConversationTurn,
    PipelineContext,
    PipelineState,
    ProcessingMode,
)


class TestPipelineState:
    def test_all_states_defined(self):
        expected = {"idle", "listening", "transcribing", "classifying", "executing", "responding", "error"}
        actual = {s.value for s in PipelineState}
        assert actual == expected

    def test_state_values_are_strings(self):
        for state in PipelineState:
            assert isinstance(state.value, str)


class TestProcessingMode:
    def test_online_mode(self):
        assert ProcessingMode.ONLINE.value == "online"

    def test_offline_mode(self):
        assert ProcessingMode.OFFLINE.value == "offline"

    def test_only_two_modes(self):
        assert len(ProcessingMode) == 2


class TestConversationTurn:
    def test_create_user_turn(self):
        turn = ConversationTurn(role="user", content="set temperature to 22")
        assert turn.role == "user"
        assert turn.content == "set temperature to 22"
        assert turn.timestamp is None

    def test_create_assistant_turn_with_timestamp(self):
        now = datetime.now()
        turn = ConversationTurn(role="assistant", content="Temperature set to 22°C.", timestamp=now)
        assert turn.role == "assistant"
        assert turn.content == "Temperature set to 22°C."
        assert turn.timestamp == now


class TestPipelineContext:
    def test_default_values(self):
        ctx = PipelineContext()
        assert ctx.state == PipelineState.IDLE
        assert ctx.mode == ProcessingMode.ONLINE
        assert ctx.transcription is None
        assert ctx.confidence == 0.0
        assert ctx.classification is None
        assert ctx.routing is None
        assert ctx.response_text is None
        assert ctx.error is None
        assert ctx.start_time is None
        assert ctx.conversation_history == []
        assert ctx.metadata == {}

    def test_custom_values(self):
        now = datetime.now()
        history = [ConversationTurn(role="user", content="hello")]
        ctx = PipelineContext(
            state=PipelineState.EXECUTING,
            mode=ProcessingMode.OFFLINE,
            transcription="set temperature to 22",
            confidence=0.95,
            classification="vehicle_control",
            routing="edge",
            start_time=now,
            conversation_history=history,
            metadata={"source": "whisper"},
        )
        assert ctx.state == PipelineState.EXECUTING
        assert ctx.mode == ProcessingMode.OFFLINE
        assert ctx.transcription == "set temperature to 22"
        assert ctx.confidence == 0.95
        assert ctx.classification == "vehicle_control"
        assert ctx.routing == "edge"
        assert ctx.start_time == now
        assert ctx.conversation_history == history
        assert ctx.metadata == {"source": "whisper"}

    def test_metadata_default_is_independent(self):
        ctx1 = PipelineContext()
        ctx2 = PipelineContext()
        ctx1.metadata["key"] = "value"
        assert "key" not in ctx2.metadata

    def test_conversation_history_default_is_independent(self):
        ctx1 = PipelineContext()
        ctx2 = PipelineContext()
        ctx1.conversation_history.append(ConversationTurn(role="user", content="hi"))
        assert len(ctx2.conversation_history) == 0


class TestAppConfig:
    def test_default_values(self):
        config = AppConfig()
        assert config.edge_target == "lmstudio"
        assert config.edge_lm_url == "http://localhost:1234/v1"
        assert config.jetson_url == "http://jetson-device:8080/v1"
        assert config.edge_model_name == "local-model"
        assert config.bedrock_profile == "losrudos"
        assert config.bedrock_model_id == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config.bedrock_region == "us-east-1"
        assert config.ping_url == "http://connectivitycheck.gstatic.com/generate_204"
        assert config.ping_interval_seconds == 3.0
        assert config.backend == "kuksa"
        assert config.kuksa_host == "localhost"
        assert config.kuksa_port == 55556
        assert config.asr_provider == "local_whisper"
        assert config.asr_model_name == "whisper-1"
        assert config.lmstudio_asr_url == "http://localhost:1234/v1"
        assert config.tts_provider == "local_pyttsx3"
        assert config.aws_tts_voice_id == "Joanna"
        assert config.critical_hr_threshold == 180
        assert config.hr_sampling_interval == 5.0
        assert config.whisper_model_size == "base"
        assert config.stt_confidence_threshold == 0.7
        assert config.classification_confidence_threshold == 0.6


class TestLoadConfig:
    def test_loads_defaults_when_no_env_vars(self, monkeypatch):
        # Clear any SPEECHLESS_ env vars
        for key in list(os.environ.keys()):
            if key.startswith("SPEECHLESS_"):
                monkeypatch.delenv(key)

        config = load_config()
        assert config.edge_target == "lmstudio"
        assert config.bedrock_profile == "losrudos"
        assert config.backend == "kuksa"
        assert config.kuksa_host == "localhost"
        assert config.kuksa_port == 55556
        assert config.ping_url == "http://connectivitycheck.gstatic.com/generate_204"
        assert config.stt_confidence_threshold == 0.7
        assert config.classification_confidence_threshold == 0.6

    def test_loads_from_environment_variables(self, monkeypatch):
        monkeypatch.setenv("SPEECHLESS_EDGE_TARGET", "jetson")
        monkeypatch.setenv("SPEECHLESS_EDGE_LM_URL", "http://custom:5000/v1")
        monkeypatch.setenv("SPEECHLESS_JETSON_URL", "http://my-jetson:9090/v1")
        monkeypatch.setenv("SPEECHLESS_BEDROCK_PROFILE", "custom-profile")
        monkeypatch.setenv("SPEECHLESS_BEDROCK_MODEL", "anthropic.claude-3-sonnet")
        monkeypatch.setenv("SPEECHLESS_BEDROCK_REGION", "eu-west-1")
        monkeypatch.setenv("SPEECHLESS_BACKEND", "simulated")
        monkeypatch.setenv("SPEECHLESS_KUKSA_HOST", "192.168.1.100")
        monkeypatch.setenv("SPEECHLESS_KUKSA_PORT", "44444")
        monkeypatch.setenv("SPEECHLESS_ASR_PROVIDER", "aws")
        monkeypatch.setenv("SPEECHLESS_TTS_PROVIDER", "aws")
        monkeypatch.setenv("SPEECHLESS_PING_URL", "http://example.com/ping")
        monkeypatch.setenv("SPEECHLESS_PING_INTERVAL", "5.0")
        monkeypatch.setenv("SPEECHLESS_CONFIDENCE_THRESHOLD", "0.8")
        monkeypatch.setenv("SPEECHLESS_CLASSIFICATION_THRESHOLD", "0.5")

        config = load_config()
        assert config.edge_target == "jetson"
        assert config.edge_lm_url == "http://custom:5000/v1"
        assert config.jetson_url == "http://my-jetson:9090/v1"
        assert config.bedrock_profile == "custom-profile"
        assert config.bedrock_model_id == "anthropic.claude-3-sonnet"
        assert config.bedrock_region == "eu-west-1"
        assert config.backend == "simulated"
        assert config.kuksa_host == "192.168.1.100"
        assert config.kuksa_port == 44444
        assert config.asr_provider == "aws"
        assert config.tts_provider == "aws"
        assert config.ping_url == "http://example.com/ping"
        assert config.ping_interval_seconds == 5.0
        assert config.stt_confidence_threshold == 0.8
        assert config.classification_confidence_threshold == 0.5

    def test_loads_edge_lm_url_from_legacy_lmstudio_env(self, monkeypatch):
        """SPEECHLESS_LMSTUDIO_URL is a fallback for SPEECHLESS_EDGE_LM_URL."""
        for key in list(os.environ.keys()):
            if key.startswith("SPEECHLESS_"):
                monkeypatch.delenv(key)

        monkeypatch.setenv("SPEECHLESS_LMSTUDIO_URL", "http://legacy:5000/v1")
        config = load_config()
        assert config.edge_lm_url == "http://legacy:5000/v1"

    def test_partial_env_override(self, monkeypatch):
        # Only override some values
        for key in list(os.environ.keys()):
            if key.startswith("SPEECHLESS_"):
                monkeypatch.delenv(key)

        monkeypatch.setenv("SPEECHLESS_EDGE_TARGET", "jetson")
        monkeypatch.setenv("SPEECHLESS_KUKSA_PORT", "12345")

        config = load_config()
        assert config.edge_target == "jetson"
        assert config.kuksa_port == 12345
        # Remaining defaults
        assert config.bedrock_profile == "losrudos"
        assert config.kuksa_host == "localhost"
