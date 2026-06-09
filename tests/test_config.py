"""Tests for speechless.config configuration loading."""

import os
from unittest.mock import patch

from speechless.config import load_config
from speechless.models import AppConfig


class TestLoadConfig:
    def test_returns_app_config(self):
        config = load_config()
        assert isinstance(config, AppConfig)

    def test_default_values_without_env(self):
        """When no env vars are set, defaults are used."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
        assert config.edge_target == "lmstudio"
        assert config.bedrock_profile == "losrudos"
        assert config.kuksa_host == "localhost"
        assert config.kuksa_port == 55555
        assert config.ping_url == "http://connectivitycheck.gstatic.com/generate_204"
        assert config.ping_interval_seconds == 3.0
        assert config.stt_confidence_threshold == 0.7
        assert config.classification_confidence_threshold == 0.6
        assert config.critical_hr_threshold == 180

    def test_edge_target_from_env(self):
        with patch.dict(os.environ, {"SPEECHLESS_EDGE_TARGET": "jetson"}):
            config = load_config()
        assert config.edge_target == "jetson"

    def test_bedrock_profile_from_env(self):
        with patch.dict(os.environ, {"SPEECHLESS_BEDROCK_PROFILE": "custom-profile"}):
            config = load_config()
        assert config.bedrock_profile == "custom-profile"

    def test_kuksa_host_and_port_from_env(self):
        with patch.dict(os.environ, {
            "SPEECHLESS_KUKSA_HOST": "192.168.1.100",
            "SPEECHLESS_KUKSA_PORT": "12345",
        }):
            config = load_config()
        assert config.kuksa_host == "192.168.1.100"
        assert config.kuksa_port == 12345

    def test_ping_url_from_env(self):
        with patch.dict(os.environ, {"SPEECHLESS_PING_URL": "http://custom-check.local/ping"}):
            config = load_config()
        assert config.ping_url == "http://custom-check.local/ping"

    def test_float_thresholds_from_env(self):
        with patch.dict(os.environ, {
            "SPEECHLESS_PING_INTERVAL": "5.0",
            "SPEECHLESS_STT_CONFIDENCE_THRESHOLD": "0.85",
            "SPEECHLESS_CLASSIFICATION_THRESHOLD": "0.75",
            "SPEECHLESS_HR_SAMPLING_INTERVAL": "10.0",
        }):
            config = load_config()
        assert config.ping_interval_seconds == 5.0
        assert config.stt_confidence_threshold == 0.85
        assert config.classification_confidence_threshold == 0.75
        assert config.hr_sampling_interval == 10.0

    def test_int_thresholds_from_env(self):
        with patch.dict(os.environ, {"SPEECHLESS_CRITICAL_HR_THRESHOLD": "200"}):
            config = load_config()
        assert config.critical_hr_threshold == 200

    def test_bedrock_model_and_region_from_env(self):
        with patch.dict(os.environ, {
            "SPEECHLESS_BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet",
            "SPEECHLESS_BEDROCK_REGION": "eu-west-1",
        }):
            config = load_config()
        assert config.bedrock_model_id == "anthropic.claude-3-sonnet"
        assert config.bedrock_region == "eu-west-1"

    def test_lmstudio_and_jetson_urls_from_env(self):
        with patch.dict(os.environ, {
            "SPEECHLESS_LMSTUDIO_URL": "http://devbox:1234/v1",
            "SPEECHLESS_JETSON_URL": "http://jetson-nano:8080/v1",
        }):
            config = load_config()
        assert config.edge_lm_url == "http://devbox:1234/v1"
        assert config.jetson_url == "http://jetson-nano:8080/v1"

    def test_whisper_model_size_from_env(self):
        with patch.dict(os.environ, {"SPEECHLESS_WHISPER_MODEL_SIZE": "large-v3"}):
            config = load_config()
        assert config.whisper_model_size == "large-v3"

    def test_edge_model_name_from_env(self):
        with patch.dict(os.environ, {"SPEECHLESS_EDGE_MODEL_NAME": "llama-3-8b"}):
            config = load_config()
        assert config.edge_model_name == "llama-3-8b"
