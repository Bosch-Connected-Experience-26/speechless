#!/usr/bin/env python3
"""Speechless Cockpit entry point.

Starts the Flask web server for the Speechless Cockpit dashboard.

Usage:
    uv run python scripts/run_dashboard.py
    uv run python scripts/run_dashboard.py --demo
    uv run python scripts/run_dashboard.py --backend simulated
    uv run python scripts/run_dashboard.py --backend kuksa --asr-provider mlx_whisper
    # Then open http://localhost:5001 in your browser
"""

import argparse
import sys
from pathlib import Path

# Ensure the project root is on the path when running directly
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from speechless.config import load_config  # noqa: E402
from speechless.dashboard.app import create_app  # noqa: E402
from speechless.dashboard.runtime import (  # noqa: E402
    VALID_ASR_PROVIDERS,
    VALID_BACKENDS,
    VALID_TTS_PROVIDERS,
    DashboardRuntime,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse dashboard CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run the Speechless cockpit dashboard.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the dashboard in scripted demo mode.",
    )
    parser.add_argument(
        "--backend",
        choices=sorted(VALID_BACKENDS),
        default=None,
        help="Vehicle backend to use. Defaults to SPEECHLESS_BACKEND or kuksa.",
    )
    parser.add_argument(
        "--asr-provider",
        choices=sorted(VALID_ASR_PROVIDERS),
        default=None,
        help="ASR provider for browser microphone input.",
    )
    parser.add_argument(
        "--tts-provider",
        choices=sorted(VALID_TTS_PROVIDERS),
        default=None,
        help="TTS provider for /api/tts.",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host interface for the Flask server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port for the Flask server.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run Flask in debug mode.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Start the dashboard server."""
    args = parse_args(argv)
    config = load_config()
    runtime = DashboardRuntime.from_config(
        config,
        mode="demo" if args.demo else "interactive",
        backend=args.backend,
        asr_provider=args.asr_provider,
        tts_provider=args.tts_provider,
        host=args.host,
        port=args.port,
        debug=args.debug,
    )

    print()
    print("=" * 60)
    print("  SPEECHLESS COCKPIT - Hybrid Voice Dashboard")
    print("  Team LosRudos | Hackathon 2025")
    print("=" * 60)
    print()
    print(f"  Mode:        {runtime.mode}")
    print(f"  Backend:     {runtime.backend}")
    print(f"  ASR:         {runtime.asr_provider}")
    print(f"  TTS:         {runtime.tts_provider}")
    print(f"  Cockpit:     http://localhost:{runtime.port}")
    print(f"  API State:   http://localhost:{runtime.port}/api/state")
    print()
    if runtime.mode == "demo":
        print("  Open the cockpit URL, then press Space or click Start Demo.")
        print(f"  Start Demo:  http://localhost:{runtime.port}/api/start-demo")
    else:
        print("  Open the cockpit URL and use the text or microphone controls.")
    print()
    print("=" * 60)
    print()

    app = create_app(config=config, runtime=runtime)
    app.run(host=runtime.host, port=runtime.port, debug=runtime.debug)


if __name__ == "__main__":
    main()
