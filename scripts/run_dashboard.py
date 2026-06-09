#!/usr/bin/env python3
"""Speechless Visual Dashboard — Entry Point.

Starts the Flask web dashboard for the voice assistant demo.

Usage:
    uv run python scripts/run_dashboard.py
    # Then open http://localhost:5001 in your browser
    # Click "Start Demo" to run the scripted scenario
"""

import sys
from pathlib import Path

# Ensure src/ is on the path when running directly
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from speechless.dashboard.app import create_app


def main() -> None:
    """Start the dashboard server."""
    print()
    print("=" * 60)
    print("  SPEECHLESS — Visual Voice Assistant Dashboard")
    print("  Team LosRudos | Hackathon 2025")
    print("=" * 60)
    print()
    print("  🌐 Dashboard:  http://localhost:5001")
    print("  📊 API State:  http://localhost:5001/api/state")
    print("  ▶  Start Demo: http://localhost:5001/api/start-demo")
    print()
    print("  Open the dashboard URL in your browser,")
    print("  then click 'Start Demo' to run the scenario.")
    print()
    print("=" * 60)
    print()

    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    main()
