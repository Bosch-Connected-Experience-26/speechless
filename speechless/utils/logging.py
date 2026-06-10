"""Structured logging for voice assistant command processing."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CommandLogEntry:
    """Structured log entry for a processed command."""

    timestamp: str
    transcription: str
    classification: str  # "vehicle_control" or "informational"
    routing_decision: str  # "edge" or "cloud"
    execution_outcome: str  # "success", "error", "timeout"
    connectivity_state: str  # "online" or "offline"
    error_detail: Optional[str] = None


class CommandLogger:
    """Structured logger for voice assistant command processing."""

    def __init__(self, logger_name: str = "speechless"):
        self.logger = logging.getLogger(logger_name)
        self._history: list[CommandLogEntry] = []

    def log_command(
        self,
        transcription: str,
        classification: str,
        routing_decision: str,
        execution_outcome: str,
        connectivity_state: str = "online",
        error_detail: Optional[str] = None,
    ) -> CommandLogEntry:
        """Log a processed command with all required fields."""
        entry = CommandLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            transcription=transcription,
            classification=classification,
            routing_decision=routing_decision,
            execution_outcome=execution_outcome,
            connectivity_state=connectivity_state,
            error_detail=error_detail,
        )
        self.logger.info(json.dumps(asdict(entry)))
        self._history.append(entry)
        return entry

    def get_history(self) -> list[CommandLogEntry]:
        """Return all logged command entries."""
        return list(self._history)

    def clear(self) -> None:
        """Clear all logged command history."""
        self._history.clear()

    @staticmethod
    def validate_entry(entry: CommandLogEntry) -> bool:
        """Validate that a log entry contains all required fields."""
        return (
            bool(entry.timestamp)
            and bool(entry.transcription)
            and entry.classification in ("vehicle_control", "informational")
            and entry.routing_decision in ("edge", "cloud")
            and entry.execution_outcome in ("success", "error", "timeout")
            and entry.connectivity_state in ("online", "offline")
        )
