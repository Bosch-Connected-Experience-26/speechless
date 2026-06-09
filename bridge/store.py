"""In-memory vehicle signal store — the always-present core of the bridge.

This is the simulator heart: it holds the current value of every signal in the
catalog and answers "did this write change anything?". It knows nothing about
WebSockets or Kuksa — transport (main.py) and the optional Kuksa adapter
(kuksa_link.py) both drive it through `apply()` and read it through `snapshot()`.

Keeping it transport-agnostic is what lets the dashboard run with no databroker
(D3): writes from `POST /command`, from UI clicks, and from a live Kuksa
subscription all funnel through the same `apply()`.
"""

from __future__ import annotations

from typing import Any, Dict

from signals import SIGNALS, coerce, default_state


class UnknownSignal(KeyError):
    """Raised when a write/read targets a path not in the catalog.

    Surfaced to the caller (D10) rather than silently defaulted — an unknown
    path is a contract error, not a value to invent.
    """


class SignalStore:
    def __init__(self) -> None:
        self._values: Dict[str, Any] = default_state()

    def snapshot(self) -> Dict[str, Any]:
        """A copy of every signal's current value (sent on WebSocket connect)."""
        return dict(self._values)

    def get(self, path: str) -> Any:
        if path not in SIGNALS:
            raise UnknownSignal(path)
        return self._values[path]

    def apply(self, path: str, value: Any) -> bool:
        """Coerce + store a value. Returns True iff the stored value changed.

        Raises UnknownSignal for paths outside the catalog. The change-detection
        return is what makes the system idempotent: setting Kuksa and receiving
        the broker's echo of the same value produces no duplicate broadcast.
        """
        if path not in SIGNALS:
            raise UnknownSignal(path)
        new_value = coerce(path, value)
        if self._values[path] == new_value:
            return False
        self._values[path] = new_value
        return True
