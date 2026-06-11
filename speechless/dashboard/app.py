"""Flask web application for the Speechless visual dashboard.

Provides:
- GET / — Main dashboard page (real-time vehicle visualization)
- GET /api/state — JSON endpoint for dashboard polling
- GET /api/start-demo — Triggers the scripted demo scenario
- GET /api/stop-demo — Stops a running demo

The dashboard polls /api/state every 500ms to update the UI.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from threading import Thread

from flask import Flask, jsonify, request, send_from_directory

from speechless.config import load_config
from speechless.dashboard.backends import VehicleBackend, create_vehicle_backend
from speechless.dashboard.interaction import DashboardInteractionService
from speechless.dashboard.providers import DashboardASR, DashboardTTS
from speechless.dashboard.runtime import DashboardRuntime
from speechless.dashboard.scenarios import (
    DemoScenarioRunner,
    build_demo_scenario,
)
from speechless.models import AppConfig

# Dashboard state — shared between Flask routes and demo thread
_dashboard_state: dict = {
    "mode": "interactive",
    "runtime": {},
    "backend": "kuksa",
    "providers": {},
    "vehicle_state": {},
    "current_command": None,
    "routing_decision": None,
    "assistant_response": None,
    "network_status": {"latency_ms": 50, "packet_loss": 0.0, "is_connected": True},
    "logs": [],
    "statistics": {},
    "sensor_history": {"speed": [], "temperature": [], "steering": []},
    "routing_history": [],
    "backend_status": {"connected": False, "host": "localhost", "port": 55556},
    "kuksa": {
        "status": {"connected": False, "host": "localhost", "port": 55556},
        "operations": [],
        "telemetry": {},
    },
}

_MAX_LOGS = 50
_runner: DemoScenarioRunner | None = None
_vehicle_backend: VehicleBackend | None = None
_interaction: DashboardInteractionService | None = None
_asr: DashboardASR | None = None
_tts: DashboardTTS | None = None
_runtime: DashboardRuntime | None = None


def _add_log(level: str, message: str, metadata: dict | None = None) -> None:
    """Add a log entry to the dashboard state."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
        "metadata": metadata or {},
    }
    _dashboard_state["logs"].insert(0, entry)
    if len(_dashboard_state["logs"]) > _MAX_LOGS:
        _dashboard_state["logs"].pop()


def _on_state_update(updates: dict) -> None:
    """Callback for scenario runner to push state updates."""
    for key, value in updates.items():
        if key == "routing_decision":
            _dashboard_state["routing_decision"] = value
            _dashboard_state["routing_history"].append(value)
            if len(_dashboard_state["routing_history"]) > 20:
                _dashboard_state["routing_history"].pop(0)
        elif key == "vehicle_state":
            _dashboard_state["vehicle_state"] = value
            # Track sensor history for potential charts
            _dashboard_state["sensor_history"]["speed"].append({
                "time": time.time(), "value": value.get("speed", 0)
            })
            _dashboard_state["sensor_history"]["temperature"].append({
                "time": time.time(), "value": value.get("temperature", 22)
            })
            _dashboard_state["sensor_history"]["steering"].append({
                "time": time.time(), "value": value.get("steering_angle", 0)
            })
            # Trim history
            for hist_key in _dashboard_state["sensor_history"]:
                if len(_dashboard_state["sensor_history"][hist_key]) > 30:
                    _dashboard_state["sensor_history"][hist_key].pop(0)
        else:
            _dashboard_state[key] = value


def _reset_dashboard_state(runtime: DashboardRuntime) -> None:
    """Reset dashboard state while preserving runtime metadata."""
    _dashboard_state.clear()
    _dashboard_state.update({
        "mode": runtime.mode,
        "runtime": runtime.to_dict(),
        "backend": runtime.backend,
        "providers": {
            "asr": runtime.asr_provider,
            "tts": runtime.tts_provider,
        },
        "vehicle_state": {},
        "current_command": None,
        "routing_decision": None,
        "assistant_response": None,
        "network_status": {"latency_ms": 50, "packet_loss": 0.0, "is_connected": True},
        "logs": [],
        "statistics": {},
        "sensor_history": {"speed": [], "temperature": [], "steering": []},
        "routing_history": [],
        "backend_status": {"connected": False, "host": "localhost", "port": 55556},
        "kuksa": {
            "status": {"connected": False, "host": "localhost", "port": 55556},
            "operations": [],
            "telemetry": {},
        },
    })


def _sync_backend_state() -> None:
    """Refresh backend status and telemetry in dashboard state."""
    if _vehicle_backend is None:
        return
    status = _vehicle_backend.get_status_dict()
    operations = _vehicle_backend.get_operations_dict()
    telemetry = _vehicle_backend.get_telemetry_dict()
    _dashboard_state["backend_status"] = status
    _dashboard_state["kuksa"]["status"] = status
    _dashboard_state["kuksa"]["operations"] = operations
    _dashboard_state["kuksa"]["telemetry"] = telemetry


def _require_interaction() -> DashboardInteractionService:
    if _interaction is None:
        raise RuntimeError("Interactive service is not initialized")
    return _interaction


def _require_asr() -> DashboardASR:
    if _asr is None:
        raise RuntimeError("ASR service is not initialized")
    return _asr


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def create_app(
    *,
    mode: str = "interactive",
    backend: str | None = None,
    asr_provider: str | None = None,
    tts_provider: str | None = None,
    config: AppConfig | None = None,
    runtime: DashboardRuntime | None = None,
) -> Flask:
    """Create and configure the Flask application."""
    global _vehicle_backend, _interaction, _asr, _tts, _runtime

    template_dir = Path(__file__).parent / "templates"
    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(template_dir),
    )

    @app.after_request
    def add_no_cache_headers(response):
        """Prevent stale dashboard assets in the in-app browser."""
        if request.path == "/" or request.path.startswith("/api/") or request.path.endswith((".css", ".js")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app_config = config or load_config()
    _runtime = runtime or DashboardRuntime.from_config(
        app_config,
        mode=mode,
        backend=backend,
        asr_provider=asr_provider,
        tts_provider=tts_provider,
    )
    _reset_dashboard_state(_runtime)

    _vehicle_backend = create_vehicle_backend(app_config, _runtime.backend)
    _interaction = DashboardInteractionService(app_config, _vehicle_backend)
    _asr = DashboardASR(app_config, provider=_runtime.asr_provider)
    _tts = DashboardTTS(app_config, provider=_runtime.tts_provider)

    if _vehicle_backend.name == "kuksa" and _vehicle_backend.is_connected:
        _add_log("INFO", "Kuksa databroker connected (gRPC :55556)", {})
    elif _vehicle_backend.name == "kuksa":
        _add_log("INFO", "Kuksa databroker not available; using dashboard simulation fallback", {})
    else:
        _add_log("INFO", "Running with simulated vehicle backend", {})

    _sync_backend_state()

    @app.route("/")
    def index():
        """Serve the cockpit dashboard HTML."""
        return send_from_directory(str(template_dir), "cockpit.html")

    @app.route("/cockpit.css")
    def cockpit_css():
        """Serve the cockpit stylesheet."""
        return send_from_directory(str(template_dir), "cockpit.css")

    @app.route("/cockpit.js")
    def cockpit_js():
        """Serve the cockpit engine script."""
        return send_from_directory(str(template_dir), "cockpit.js")

    @app.route("/scenario.js")
    def scenario_js():
        """Serve the scripted demo timeline."""
        return send_from_directory(str(template_dir), "scenario.js")

    @app.route("/api/config")
    def get_config():
        """Return dashboard runtime configuration."""
        return jsonify({
            "runtime": _runtime.to_dict() if _runtime else {},
            "mode": _runtime.mode if _runtime else "interactive",
            "backend": _vehicle_backend.name if _vehicle_backend else None,
            "providers": _dashboard_state["providers"],
            "models": {
                "asr": {
                    "provider": _runtime.asr_provider if _runtime else app_config.asr_provider,
                    "mlx_whisper_model": app_config.mlx_whisper_model,
                    "lmstudio_url": app_config.lmstudio_asr_url,
                    "openai_compatible_model": app_config.asr_model_name,
                },
                "bedrock": {
                    "enabled": _env_enabled("SPEECHLESS_BEDROCK_ENABLED"),
                    "profile": app_config.bedrock_profile,
                    "region": app_config.bedrock_region,
                    "model_id": app_config.bedrock_model_id,
                },
                "edge_llm": {
                    "enabled": _env_enabled("SPEECHLESS_EDGE_LLM_ENABLED"),
                    "target": app_config.edge_target,
                    "url": app_config.edge_lm_url
                    if app_config.edge_target == "lmstudio"
                    else app_config.jetson_url,
                    "model_name": app_config.edge_model_name,
                },
            },
        })

    @app.route("/api/state")
    def get_state():
        """Return current dashboard state as JSON."""
        _sync_backend_state()
        return jsonify(_dashboard_state)

    @app.route("/api/start-demo")
    def start_demo():
        """Start the demo scenario in a background thread."""
        global _runner

        if _runtime is None or _runtime.mode != "demo":
            return jsonify({
                "status": "Demo mode is disabled",
                "mode": _runtime.mode if _runtime else "interactive",
            }), 409

        if _runner is not None and _runner.is_running:
            return jsonify({"status": "Demo already running"})

        _reset_dashboard_state(_runtime)
        _sync_backend_state()

        _runner = DemoScenarioRunner(
            vehicle=_vehicle_backend.vehicle if _vehicle_backend else None,
            on_log=_add_log,
            on_state_update=_on_state_update,
            kuksa_bridge=getattr(_vehicle_backend, "kuksa_bridge", None),
        )

        def run_async_demo():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                scenario = build_demo_scenario()
                loop.run_until_complete(_runner.run_scenario(scenario))
                loop.close()
            except Exception as e:
                _add_log("ERROR", f"Demo crashed: {type(e).__name__}: {e}", {})
                import traceback
                traceback.print_exc()

        thread = Thread(target=run_async_demo, daemon=True)
        thread.start()

        return jsonify({
            "status": "Demo started",
            "backend": _vehicle_backend.name if _vehicle_backend else None,
            "backend_connected": _vehicle_backend.is_connected if _vehicle_backend else False,
        })

    @app.route("/api/stop-demo")
    def stop_demo():
        """Stop the running demo."""
        if _runner is not None:
            _runner.stop()
            return jsonify({"status": "Demo stopped"})
        return jsonify({"status": "No demo running"})

    @app.route("/api/command/text", methods=["POST"])
    def command_text():
        """Process a typed dashboard command."""
        if _runtime is not None and _runtime.mode != "interactive":
            return jsonify({"error": "Text commands are only enabled in interactive mode"}), 409

        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "")).strip()
        if not text:
            return jsonify({"error": "Missing command text"}), 400

        try:
            updates = asyncio.run(_require_interaction().process_text(
                text,
                network_status=_dashboard_state["network_status"],
                transcription_source="text",
            ))
            _on_state_update(updates)
            _add_log("VOICE", f"Driver: {text}", {"source": "text"})
            _add_log("ROUTING", updates["routing_decision"]["response"], {
                "route": updates["routing_decision"]["executed_on"],
                "latency_ms": updates["routing_decision"]["latency_ms"],
            })
            _sync_backend_state()
            return jsonify({"status": "ok", "updates": updates, "state": _dashboard_state})
        except Exception as e:
            _add_log("ERROR", f"Command failed: {type(e).__name__}: {e}", {})
            return jsonify({"error": str(e)}), 500

    @app.route("/api/command/audio", methods=["POST"])
    def command_audio():
        """Transcribe browser audio and process the resulting command."""
        if _runtime is not None and _runtime.mode != "interactive":
            return jsonify({"error": "Audio commands are only enabled in interactive mode"}), 409

        if request.files:
            wav_bytes = next(iter(request.files.values())).read()
        else:
            wav_bytes = request.get_data()

        if not wav_bytes:
            return jsonify({"error": "Missing audio data"}), 400

        try:
            transcription = _require_asr().transcribe_wav(wav_bytes)
            if transcription.error_message or not transcription.text.strip():
                return jsonify({
                    "error": transcription.error_message or "No speech detected",
                    "transcription": transcription.__dict__,
                }), 422

            updates = asyncio.run(_require_interaction().process_text(
                transcription.text,
                network_status=_dashboard_state["network_status"],
                transcription_source=transcription.source,
                transcription_confidence=transcription.confidence,
            ))
            _on_state_update(updates)
            _add_log("VOICE", f"Transcribed: {transcription.text}", {
                "source": transcription.source,
                "confidence": transcription.confidence,
            })
            _add_log("ROUTING", updates["routing_decision"]["response"], {
                "route": updates["routing_decision"]["executed_on"],
                "latency_ms": updates["routing_decision"]["latency_ms"],
            })
            _sync_backend_state()
            return jsonify({
                "status": "ok",
                "transcription": transcription.__dict__,
                "updates": updates,
                "state": _dashboard_state,
            })
        except Exception as e:
            _add_log("ERROR", f"Audio command failed: {type(e).__name__}: {e}", {})
            return jsonify({"error": str(e)}), 500

    @app.route("/api/command/server-audio", methods=["POST"])
    def command_server_audio():
        """Record from the server microphone and process the resulting command."""
        if _runtime is not None and _runtime.mode != "interactive":
            return jsonify({"error": "Audio commands are only enabled in interactive mode"}), 409

        payload = request.get_json(silent=True) or {}
        duration = float(payload.get("duration_seconds", 4.0))
        duration = max(1.0, min(duration, 8.0))

        try:
            from speechless.speech.capture import AudioCapture

            capture = AudioCapture(chunk_duration=duration)
            segment = capture.record()
            wav_bytes = _require_asr().samples_to_wav(segment.samples, segment.sample_rate)
            transcription = _require_asr().transcribe_wav(wav_bytes)
            if transcription.error_message or not transcription.text.strip():
                return jsonify({
                    "error": transcription.error_message or "No speech detected",
                    "transcription": transcription.__dict__,
                }), 422

            updates = asyncio.run(_require_interaction().process_text(
                transcription.text,
                network_status=_dashboard_state["network_status"],
                transcription_source=f"server_{transcription.source}",
                transcription_confidence=transcription.confidence,
            ))
            _on_state_update(updates)
            _add_log("VOICE", f"Server mic transcribed: {transcription.text}", {
                "source": transcription.source,
                "confidence": transcription.confidence,
            })
            _add_log("ROUTING", updates["routing_decision"]["response"], {
                "route": updates["routing_decision"]["executed_on"],
                "latency_ms": updates["routing_decision"]["latency_ms"],
            })
            _sync_backend_state()
            return jsonify({
                "status": "ok",
                "transcription": transcription.__dict__,
                "updates": updates,
                "state": _dashboard_state,
            })
        except Exception as e:
            _add_log("ERROR", f"Server audio command failed: {type(e).__name__}: {e}", {})
            return jsonify({"error": str(e)}), 500

    @app.route("/api/reset", methods=["POST"])
    def reset_state():
        """Reset interactive dashboard state."""
        if _runtime is None:
            return jsonify({"error": "Dashboard runtime is not initialized"}), 500
        if _interaction:
            _interaction.reset()
        _reset_dashboard_state(_runtime)
        _sync_backend_state()
        return jsonify({"status": "reset", "state": _dashboard_state})

    @app.route("/api/tts", methods=["POST"])
    def speak_tts():
        """Speak text through the configured TTS provider."""
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "")).strip()
        if not text:
            text = str(_dashboard_state.get("assistant_response") or "").strip()
        if not text:
            return jsonify({"error": "Missing text"}), 400
        if _tts is None:
            return jsonify({"error": "TTS service is not initialized"}), 500
        return jsonify({"status": "queued", "tts": _tts.speak_async(text)})

    @app.route("/api/kuksa/reconnect")
    def kuksa_reconnect():
        """Try to reconnect to the configured vehicle backend."""
        if _vehicle_backend:
            success = _vehicle_backend.try_reconnect()
            if success:
                _add_log("INFO", "Vehicle backend reconnected successfully", {})
            else:
                _add_log("INFO", "Vehicle backend reconnection failed", {})
            _sync_backend_state()
            return jsonify({"connected": success})
        return jsonify({"connected": False})

    @app.route("/api/backend/reconnect")
    def backend_reconnect():
        """Alias for reconnecting the configured vehicle backend."""
        return kuksa_reconnect()

    return app
