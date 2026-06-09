"""Tests for speechless.models data models."""

from datetime import datetime

from speechless.models import AppConfig, PipelineContext, PipelineState, ProcessingMode


class TestPipelineState:
    def test_all_states_defined(self):
        expected = {"idle", "listening", "transcribing", "classifying", "executing", "responding", "error"}
        actual = {s.value for s in PipelineState}
        assert actual == expected

    def test_state_values_are_strings(self):
        for state in PipelineState:
            assert isinstance(state.value, str)


class TestProcessingMode:
    def test_modes_defined(self):
        assert ProcessingMode.ONLINE.value == "online"
        assert ProcessingMode.OFFLINE.value == "offline"

    def test_exactly_two_modes(self):
        assert len(ProcessingMode) == 2


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
        assert ctx.metadata == {}

    def test_custom_values(self):
        now = datetime.now()
        ctx = PipelineContext(
            state=PipelineState.EXECUTING,
            mode=ProcessingMode.OFFLINE,
            transcription="set temperature to 22",
            confidence=0.95,
            classification="vehicle_control",
            routing="edge",
            start_time=now,
            metadata={"intent": "hvac"},
        )
        assert ctx.state == PipelineState.EXECUTING
        assert ctx.mode == ProcessingMode.OFFLINE
        assert ctx.transcription == "set temperature to 22"
        assert ctx.confidence == 0.95
        assert ctx.classification == "vehicle_control"
        assert ctx.routing == "edge"
        assert ctx.start_time == now
        assert ctx.metadata == {"intent": "hvac"}

    def test_metadata_default_is_independent(self):
        """Each instance should get its own metadata dict."""
        ctx1 = PipelineContext()
        ctx2 = PipelineContext()
        ctx1.metadata["key"] = "value"
        assert "key" not in ctx2.metadata


class TestAppConfig:
    def test_default_values(self):
        config = AppConfig()
        assert config.edge_target == "lmstudio"
        assert config.lmstudio_url == "http://localhost:1234/v1"
        assert config.jetson_url == "http://jetson-device:8080/v1"
        assert config.edge_model_name == "local-model"
        assert config.bedrock_profile == "losrudos"
        assert config.bedrock_model_id == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config.bedrock_region == "us-east-1"
        assert config.ping_url == "http://connectivitycheck.gstatic.com/generate_204"
        assert config.ping_interval_seconds == 3.0
        assert config.kuksa_host == "localhost"
        assert config.kuksa_port == 55555
        assert config.critical_hr_threshold == 180
        assert config.hr_sampling_interval == 5.0
        assert config.whisper_model_size == "base"
        assert config.stt_confidence_threshold == 0.7
        assert config.classification_confidence_threshold == 0.6

    def test_custom_edge_target(self):
        config = AppConfig(edge_target="jetson")
        assert config.edge_target == "jetson"
