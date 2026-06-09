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
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Optional

from flask import Flask, jsonify, send_from_directory

from speechless.dashboard.kuksa_bridge import KuksaBridge
from speechless.dashboard.scenarios import (
    DemoScenarioRunner,
    build_demo_scenario,
)
from speechless.edge.simulated_vehicle import SimulatedVehicleControl


# Dashboard state — shared between Flask routes and demo thread
_dashboard_state: dict = {
    "vehicle_state": {},
    "current_command": None,
    "routing_decision": None,
    "network_status": {"latency_ms": 50, "packet_loss": 0.0, "is_connected": True},
    "logs": [],
    "statistics": {},
    "sensor_history": {"speed": [], "temperature": [], "steering": []},
    "routing_history": [],
    "kuksa": {
        "status": {"connected": False, "host": "localhost", "port": 55555},
        "operations": [],
        "telemetry": {},
    },
}

_MAX_LOGS = 50
_runner: Optional[DemoScenarioRunner] = None
_kuksa_bridge: Optional[KuksaBridge] = None


def _add_log(level: str, message: str, metadata: Optional[dict] = None) -> None:
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


def create_app() -> Flask:
    """Create and configure the Flask application."""
    global _kuksa_bridge

    template_dir = Path(__file__).parent / "templates"
    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(template_dir),
    )

    # Initialize Kuksa bridge (auto-connects if databroker is running)
    _kuksa_bridge = KuksaBridge(auto_connect=True)
    if _kuksa_bridge.is_connected:
        _add_log("INFO", "✅ Kuksa databroker connected (gRPC :55555)", {})
    else:
        _add_log("INFO", "⚠️ Kuksa databroker not available — running in simulated mode", {})

    _dashboard_state["kuksa"]["status"] = _kuksa_bridge.get_status_dict()

    @app.route("/")
    def index():
        """Serve the dashboard HTML."""
        return send_from_directory(str(template_dir), "dashboard.html")

    @app.route("/api/state")
    def get_state():
        """Return current dashboard state as JSON."""
        # Update Kuksa status on each poll
        if _kuksa_bridge:
            _dashboard_state["kuksa"]["status"] = _kuksa_bridge.get_status_dict()
            _dashboard_state["kuksa"]["operations"] = _kuksa_bridge.get_operations_dict()
            _dashboard_state["kuksa"]["telemetry"] = _kuksa_bridge.get_telemetry_dict()
        return jsonify(_dashboard_state)

    @app.route("/api/start-demo")
    def start_demo():
        """Start the demo scenario in a background thread."""
        global _runner

        if _runner is not None and _runner.is_running:
            return jsonify({"status": "Demo already running"})

        # Reset state
        _dashboard_state["logs"] = []
        _dashboard_state["routing_history"] = []
        _dashboard_state["sensor_history"] = {"speed": [], "temperature": [], "steering": []}
        _dashboard_state["vehicle_state"] = {}
        _dashboard_state["current_command"] = None
        _dashboard_state["routing_decision"] = None
        _dashboard_state["statistics"] = {}

        vehicle = SimulatedVehicleControl()
        _runner = DemoScenarioRunner(
            vehicle=vehicle,
            on_log=_add_log,
            on_state_update=_on_state_update,
            kuksa_bridge=_kuksa_bridge,
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

        return jsonify({"status": "Demo started", "kuksa_connected": _kuksa_bridge.is_connected if _kuksa_bridge else False})

    @app.route("/api/stop-demo")
    def stop_demo():
        """Stop the running demo."""
        if _runner is not None:
            _runner.stop()
            return jsonify({"status": "Demo stopped"})
        return jsonify({"status": "No demo running"})

    @app.route("/api/kuksa/reconnect")
    def kuksa_reconnect():
        """Try to reconnect to Kuksa databroker."""
        if _kuksa_bridge:
            success = _kuksa_bridge.try_reconnect()
            if success:
                _add_log("INFO", "✅ Kuksa reconnected successfully", {})
            else:
                _add_log("INFO", "❌ Kuksa reconnection failed", {})
            return jsonify({"connected": success})
        return jsonify({"connected": False})

    return app
