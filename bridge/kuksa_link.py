"""Optional Eclipse Kuksa adapter — the bridge's gRPC side.

Import-guarded by design (D3, D5): if `kuksa-client` is not installed OR no
`KUKSA_ADDRESS` is configured, the bridge runs as a pure in-memory simulator and
this module's `available` is False. When a databroker IS reachable, this adapter:

  * subscribes to the catalog's signals and pushes every change into the store
    (so a value set by ANY client — e.g. the `kuksa-client` CLI — animates the
    dashboard), and
  * writes commanded values back to the databroker via `set_current_values`.

API grounded against kuksa_client/grpc/aio.py:
  - `async with VSSClient(host, port) as client:`            (connects on enter)
  - `async for updates in client.subscribe_current_values(paths):`
        updates is Dict[str, Datapoint]; use `dp.value`      (aio.py:293)
  - `await client.set_current_values({path: Datapoint(v)})`  (aio.py:220)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Iterable

logger = logging.getLogger("bridge.kuksa")

# Import guard (D3/F2): a missing kuksa-client must not break the simulator.
try:
    from kuksa_client.grpc import Datapoint
    from kuksa_client.grpc.aio import VSSClient

    _KUKSA_IMPORTABLE = True
except ImportError:  # pragma: no cover - exercised only when dep absent
    Datapoint = None  # type: ignore
    VSSClient = None  # type: ignore
    _KUKSA_IMPORTABLE = False


# Async callback the adapter calls for every value it observes from the broker.
OnUpdate = Callable[[str, object], Awaitable[None]]


class KuksaLink:
    """Lifecycle wrapper around a single VSSClient used for subscribe + set."""

    def __init__(
        self,
        address: str | None,
        port: int,
        paths: Iterable[str],
        on_update: OnUpdate,
        *,
        reconnect_seconds: float = 3.0,
    ) -> None:
        self._address = address
        self._port = port
        self._paths = list(paths)
        self._on_update = on_update
        self._reconnect_seconds = reconnect_seconds
        self._client = None  # set while connected; used by set_value
        self._connected = asyncio.Event()
        self._task: asyncio.Task | None = None

    @property
    def available(self) -> bool:
        """True only if the client is importable AND an address was configured."""
        return _KUKSA_IMPORTABLE and bool(self._address)

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def start(self) -> None:
        if not self.available:
            logger.info(
                "Kuksa adapter inactive (importable=%s, address=%r) - "
                "running as in-memory simulator.",
                _KUKSA_IMPORTABLE,
                self._address,
            )
            return
        self._task = asyncio.create_task(self._run(), name="kuksa-link")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def set_value(self, path: str, value: object) -> bool:
        """Write a value to the databroker. Returns True on success.

        Failures are logged and surfaced as a False return (D5/D10) — never
        swallowed into a fake success. In simulator mode this is a no-op (the
        store was already updated by the caller), returning False.
        """
        if not self.available or self._client is None or not self.connected:
            return False
        try:
            await self._client.set_current_values({path: Datapoint(value)})
            return True
        except Exception:  # noqa: BLE001 - broker/network errors are expected at runtime
            logger.exception("Kuksa set_current_values failed for %s=%r", path, value)
            return False

    async def _run(self) -> None:
        """Connect, subscribe, and fan changes into the store; reconnect on loss."""
        while True:
            try:
                async with VSSClient(self._address, self._port) as client:
                    self._client = client
                    self._connected.set()
                    logger.info("Kuksa connected at %s:%s", self._address, self._port)
                    async for updates in client.subscribe_current_values(self._paths):
                        for path, dp in updates.items():
                            if dp is None or dp.value is None:
                                continue
                            await self._on_update(path, dp.value)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - reconnect on any broker/network error
                logger.exception("Kuksa link error; reconnecting in %ss", self._reconnect_seconds)
            finally:
                self._connected.clear()
                self._client = None
            await asyncio.sleep(self._reconnect_seconds)
