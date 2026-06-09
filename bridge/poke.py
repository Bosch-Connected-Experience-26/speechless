#!/usr/bin/env python3
"""Fire example commands at the bridge so the dashboard animates without the
voice pipeline (D9 — the standalone-demo + stage-fallback path, R5).

Each entry mimics what the voice AI's agentic router would POST after deciding
edge vs cloud and measuring its own latency. Safety-critical actions are shown
on the fast EDGE path; richer intents on the CLOUD path.

    python poke.py                 # run the scripted scene once
    python poke.py --loop          # repeat forever (great for a looping demo)
    python poke.py --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request

# (intent, path, value, route, latency_ms) — latency_ms is the voice-reported
# number; edge commands are fast, cloud commands carry network round-trip cost.
SCENE = [
    ("Lock the doors", "Vehicle.Cabin.Door.Row1.DriverSide.IsLocked", True, "edge", 7),
    ("Turn on the headlights", "Vehicle.Body.Lights.Beam.Low.IsOn", True, "edge", 9),
    ("Signal left", "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling", True, "edge", 6),
    ("Set the cabin to 21 degrees", "Vehicle.Cabin.HVAC.Station.Row1.Left.Temperature", 21.0, "cloud", 280),
    ("Turn on the AC", "Vehicle.Cabin.HVAC.IsAirConditioningActive", True, "cloud", 240),
    ("Crack the driver window halfway", "Vehicle.Cabin.Door.Row1.DriverSide.Window.Position", 50, "cloud", 310),
    ("We're moving", "Vehicle.Speed", 48.0, "edge", 8),
    ("Stop signalling", "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling", False, "edge", 5),
    ("Unlock for the passenger", "Vehicle.Cabin.Door.Row1.PassengerSide.IsLocked", False, "cloud", 265),
    ("Close the window", "Vehicle.Cabin.Door.Row1.DriverSide.Window.Position", 0, "cloud", 295),
]


def send(url: str, intent: str, path: str, value, route: str, latency_ms: float) -> None:
    payload = json.dumps(
        {"intent": intent, "path": path, "value": value, "route": route, "latency_ms": latency_ms}
    ).encode()
    req = urllib.request.Request(
        url.rstrip("/") + "/command", data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())
    bridge_ms = body.get("bridge_ms", "?")
    tag = route.upper().ljust(5)
    print(f"  [{tag}] {intent:<38} voice={latency_ms:>4}ms  bridge={bridge_ms}ms")


def run_scene(url: str, delay: float) -> None:
    print(f"Poking bridge at {url}")
    for intent, path, value, route, latency_ms in SCENE:
        try:
            send(url, intent, path, value, route, latency_ms)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"  ! failed to send {intent!r}: {exc}")
        time.sleep(delay)


def main() -> None:
    ap = argparse.ArgumentParser(description="Fire demo commands at the vehicle bridge.")
    ap.add_argument("--url", default="http://localhost:8000", help="bridge base URL")
    ap.add_argument("--loop", action="store_true", help="repeat the scene forever")
    ap.add_argument("--delay", type=float, default=1.2, help="seconds between commands")
    args = ap.parse_args()

    while True:
        run_scene(args.url, args.delay)
        if not args.loop:
            break
        print("--- replaying ---")
        time.sleep(2.0)


if __name__ == "__main__":
    main()
