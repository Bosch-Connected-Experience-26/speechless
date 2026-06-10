"""Tests for dashboard runtime modes and interactive endpoints."""

from __future__ import annotations

import numpy as np
import pytest

from scripts.run_dashboard import parse_args
from speechless.dashboard.app import create_app
from speechless.dashboard.providers import ASRProviderResult, DashboardASR
from speechless.models import AppConfig


class TestDashboardCLI:
    def test_default_cli_is_interactive(self):
        args = parse_args([])
        assert args.demo is False
        assert args.backend is None

    def test_demo_flag_enables_demo_mode(self):
        args = parse_args(["--demo", "--backend", "simulated"])
        assert args.demo is True
        assert args.backend == "simulated"

    def test_kuksa_flag_is_not_supported(self):
        with pytest.raises(SystemExit):
            parse_args(["--kuksa"])


class TestDashboardAppModes:
    def test_interactive_config_endpoint(self):
        app = create_app(config=AppConfig(), mode="interactive", backend="simulated")

        response = app.test_client().get("/api/config")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["mode"] == "interactive"
        assert payload["backend"] == "simulated"
        assert payload["providers"]["asr"] == "local_whisper"

    def test_interactive_mode_blocks_start_demo(self):
        app = create_app(config=AppConfig(), mode="interactive", backend="simulated")

        response = app.test_client().get("/api/start-demo")

        assert response.status_code == 409
        assert response.get_json()["status"] == "Demo mode is disabled"

    def test_demo_mode_allows_start_demo(self):
        app = create_app(config=AppConfig(), mode="demo", backend="simulated")
        client = app.test_client()

        response = client.get("/api/start-demo")
        client.get("/api/stop-demo")

        assert response.status_code == 200
        assert response.get_json()["status"] == "Demo started"


class TestInteractiveCommands:
    def test_text_vehicle_command_routes_to_edge(self):
        app = create_app(config=AppConfig(), mode="interactive", backend="simulated")

        response = app.test_client().post(
            "/api/command/text",
            json={"text": "Set temperature to 24 degrees"},
        )

        payload = response.get_json()
        decision = payload["updates"]["routing_decision"]
        vehicle = payload["updates"]["vehicle_state"]
        assert response.status_code == 200
        assert decision["executed_on"] == "edge"
        assert decision["success"] is True
        assert vehicle["temperature"] == 24.0

    def test_text_informational_command_uses_cloud_when_online(self):
        app = create_app(config=AppConfig(), mode="interactive", backend="simulated")

        response = app.test_client().post(
            "/api/command/text",
            json={"text": "What food options are nearby?"},
        )

        decision = response.get_json()["updates"]["routing_decision"]
        assert response.status_code == 200
        assert decision["executed_on"] == "cloud"
        assert decision["success"] is True
        assert "Pasta" in decision["response"]

    def test_audio_command_uses_transcription_path(self, monkeypatch):
        def fake_transcribe(self, wav_bytes):
            return ASRProviderResult(
                text="Turn on the lights",
                confidence=0.9,
                source="test_asr",
            )

        monkeypatch.setattr(DashboardASR, "transcribe_wav", fake_transcribe)
        app = create_app(config=AppConfig(), mode="interactive", backend="simulated")

        response = app.test_client().post(
            "/api/command/audio",
            data=b"fake wav bytes",
            content_type="audio/wav",
        )

        payload = response.get_json()
        assert response.status_code == 200
        assert payload["transcription"]["text"] == "Turn on the lights"
        assert payload["updates"]["routing_decision"]["executed_on"] == "edge"

    def test_server_audio_command_records_and_transcribes(self, monkeypatch):
        class FakeSegment:
            samples = np.zeros(16000, dtype=np.float32)
            sample_rate = 16000
            duration_seconds = 1.0

        class FakeCapture:
            def __init__(self, chunk_duration):
                self.chunk_duration = chunk_duration

            def record(self):
                return FakeSegment()

        def fake_transcribe(self, wav_bytes):
            return ASRProviderResult(
                text="Lock the doors",
                confidence=0.9,
                source="test_asr",
            )

        monkeypatch.setattr("speechless.speech.capture.AudioCapture", FakeCapture)
        monkeypatch.setattr(DashboardASR, "transcribe_wav", fake_transcribe)
        app = create_app(config=AppConfig(), mode="interactive", backend="simulated")

        response = app.test_client().post(
            "/api/command/server-audio",
            json={"duration_seconds": 1},
        )

        payload = response.get_json()
        assert response.status_code == 200
        assert payload["transcription"]["text"] == "Lock the doors"
        assert payload["updates"]["routing_decision"]["executed_on"] == "edge"

    def test_reset_endpoint_clears_statistics(self):
        app = create_app(config=AppConfig(), mode="interactive", backend="simulated")
        client = app.test_client()
        client.post("/api/command/text", json={"text": "Lock the doors"})

        response = client.post("/api/reset")

        assert response.status_code == 200
        assert response.get_json()["state"]["statistics"] == {}
