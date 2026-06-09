"""Structured command logging for the Speechless voice assistant pipeline."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CommandLogEntry:
    """A structured log entry for a single processed voice command.

    Attributes:
        timestamp: ISO 8601 formatted timestamp of when the command was processed.
        transcription: The transcribed text from speech-to-text.
        classification: The classification result (e.g., "vehicle_control", "informational").
        routing_decision: Where the command was routed (e.g., "edge", "cloud").
        execution_outcome: The result of command execution (e.g., "success", "error: ...").
        connectivity_state: Network state at time of processing (e.g., "online", "offline").
    """

    timestamp: str
    transcription: str
    classification: str
    routing_decision: str
    execution_outcome: str
    connectivity_state: str


class CommandLogger:
    """In-memory structured logger for voice command processing.

    Stores CommandLogEntry instances for debugging and demo purposes.
    """

    def __init__(self) -> None:
        self._entries: list[CommandLogEntry] = []

    def log_command(self, entry: CommandLogEntry) -> None:
        """Append a command log entry to the in-memory log.

        Args:
            entry: A fully populated CommandLogEntry to record.
        """
        self._entries.append(entry)

    def get_log(self) -> list[CommandLogEntry]:
        """Return all logged command entries in chronological order.

        Returns:
            A list of CommandLogEntry instances, oldest first.
        """
        return list(self._entries)

    def clear(self) -> None:
        """Clear all stored log entries."""
        self._entries.clear()

    @staticmethod
    def create_entry(
        transcription: str,
        classification: str,
        routing_decision: str,
        execution_outcome: str,
        connectivity_state: str,
        timestamp: Optional[str] = None,
    ) -> CommandLogEntry:
        """Factory method to create a CommandLogEntry with auto-generated timestamp.

        Args:
            transcription: The transcribed command text.
            classification: Classification result.
            routing_decision: Routing destination.
            execution_outcome: Outcome of execution.
            connectivity_state: Current connectivity state.
            timestamp: Optional ISO timestamp. If None, uses current UTC time.

        Returns:
            A new CommandLogEntry instance.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        return CommandLogEntry(
            timestamp=timestamp,
            transcription=transcription,
            classification=classification,
            routing_decision=routing_decision,
            execution_outcome=execution_outcome,
            connectivity_state=connectivity_state,
        )
