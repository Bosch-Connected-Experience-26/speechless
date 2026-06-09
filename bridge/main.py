"""FastAPI bridge: Kuksa/simulator state  <->  browser dashboard.

The single component that speaks both sides (D2):
  * inbound  — `POST /command` (voice AI entry point) and WebSocket `set`
               (dashboard car clicks) write vehicle signals;
  * outbound — every signal change is pushed to all connected dashboards over
               WebSocket as an `update`, and each command also as a `command`
               event carrying the voice-reported route/latency PLUS a
               bridge-measured `bridge_ms` (D12).

Run:
    uvicorn main:app --port 8000            # pure simulator (no databroker)
    KUKSA_ADDRESS=127.0.0.1 uvicorn main:app --port 8000   # bridge a real Kuksa
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from kuksa_link import KuksaLink
from signals import PATHS, SIGNALS
from store import SignalStore, UnknownSignal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bridge")

KUKSA_ADDRESS = os.getenv("KUKSA_ADDRESS")  # unset -> pure simulator (D3)
KUKSA_PORT = int(os.getenv("KUKSA_PORT", "55555"))


def now_ms() -> int:
    return int(time.time() * 1000)


class ConnectionManager:
    """Tracks connected dashboards and fans events out to all of them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - a dead socket must not block others
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


class CommandIn(BaseModel):
    """Voice-AI command payload (D4/D11).

    `route`/`latency_ms` are the voice router's OWN decision — produced by the
    agentic router, not by this bridge (D11). The bridge renders them faithfully
    and adds its own measured `bridge_ms` (D12) so the panel has one real datum.
    """

    path: str
    value: Any
    intent: Optional[str] = None
    route: Optional[str] = None  # "edge" | "cloud" (voice-asserted)
    latency_ms: Optional[float] = None  # voice-reported


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SignalStore()
    manager = ConnectionManager()

    async def ingest(path: str, value: Any) -> bool:
        """Apply a value to the store and broadcast an `update` if it changed.

        The single funnel for every value source (D3): local writes and the
        Kuksa subscription both land here. Idempotent — an unchanged write
        produces no broadcast, which breaks the set->echo loop in Kuksa mode.
        """
        try:
            changed = store.apply(path, value)
        except UnknownSignal:
            logger.warning("ignoring update for unknown signal %s", path)
            return False
        if changed:
            await manager.broadcast(
                {"type": "update", "path": path, "value": store.get(path), "ts": now_ms()}
            )
        return changed

    link = KuksaLink(KUKSA_ADDRESS, KUKSA_PORT, PATHS, ingest)

    app.state.store = store
    app.state.manager = manager
    app.state.link = link
    app.state.ingest = ingest

    link.start()
    try:
        yield
    finally:
        await link.stop()


app = FastAPI(title="LosRudos Vehicle Bridge", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def apply_command(
    *,
    path: str,
    value: Any,
    intent: Optional[str],
    route: Optional[str],
    latency_ms: Optional[float],
    source: str,
) -> dict:
    """Shared write path for POST /command and WebSocket commands.

    Validates the path, measures bridge-side latency, updates the store,
    best-effort-writes the databroker, and broadcasts the `command` event.
    Raises UnknownSignal for an out-of-catalog path (D10) — caller surfaces it.
    """
    store: SignalStore = app.state.store
    manager: ConnectionManager = app.state.manager
    link: KuksaLink = app.state.link
    ingest = app.state.ingest

    store.get(path)  # raises UnknownSignal before we touch anything

    t0 = time.perf_counter()
    await ingest(path, value)
    kuksa_ok = await link.set_value(path, value)
    bridge_ms = round((time.perf_counter() - t0) * 1000, 2)

    event = {
        "type": "command",
        "intent": intent,
        "route": route,  # voice-asserted (D11)
        "latency_ms": latency_ms,  # voice-reported (D11)
        "bridge_ms": bridge_ms,  # bridge-measured (D12)
        "path": path,
        "value": store.get(path),
        "source": source,
        "kuksa_ok": kuksa_ok,
        "ts": now_ms(),
    }
    await manager.broadcast(event)
    return event


@app.get("/healthz")
async def healthz() -> dict:
    link: KuksaLink = app.state.link
    return {
        "status": "ok",
        "mode": "kuksa" if link.available else "simulator",
        "kuksa_connected": link.connected,
    }


@app.get("/signals")
async def get_signals() -> dict:
    """The authoritative catalog + current values (frontend can fetch this)."""
    store: SignalStore = app.state.store
    return {"signals": SIGNALS, "values": store.snapshot()}


@app.post("/command")
async def post_command(cmd: CommandIn) -> dict:
    """Voice-AI entry point. One call per executed action (D4)."""
    try:
        event = await apply_command(
            path=cmd.path,
            value=cmd.value,
            intent=cmd.intent,
            route=cmd.route,
            latency_ms=cmd.latency_ms,
            source="voice",
        )
    except UnknownSignal:
        return {"ok": False, "error": f"unknown signal: {cmd.path}"}
    return {"ok": True, "bridge_ms": event["bridge_ms"], "event": event}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    manager: ConnectionManager = app.state.manager
    store: SignalStore = app.state.store
    await manager.connect(ws)
    # Snapshot on connect so a freshly-opened dashboard renders current state (D4).
    await ws.send_json({"type": "snapshot", "signals": store.snapshot(), "ts": now_ms()})
    try:
        while True:
            msg = await ws.receive_json()
            await _handle_ws_message(ws, msg)
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:  # noqa: BLE001 - never let one bad frame kill the socket (D10)
        logger.exception("websocket handler error")
        manager.disconnect(ws)


async def _handle_ws_message(ws: WebSocket, msg: Any) -> None:
    """Dispatch a single inbound WebSocket frame. Malformed frames are surfaced,
    not fatal (D10)."""
    if not isinstance(msg, dict):
        await ws.send_json({"type": "error", "error": "expected a JSON object"})
        return
    mtype = msg.get("type")
    if mtype not in ("set", "command"):
        await ws.send_json({"type": "error", "error": f"unknown message type: {mtype!r}"})
        return
    path = msg.get("path")
    if not isinstance(path, str):
        await ws.send_json({"type": "error", "error": "missing 'path'"})
        return
    try:
        await apply_command(
            path=path,
            value=msg.get("value"),
            intent=msg.get("intent", "(dashboard)" if mtype == "set" else None),
            route=msg.get("route"),
            latency_ms=msg.get("latency_ms"),
            source="dashboard" if mtype == "set" else "voice",
        )
    except UnknownSignal:
        await ws.send_json({"type": "error", "error": f"unknown signal: {path}"})
