"""Tests for the structured command logging module."""

from datetime import datetime, timezone

import pytest

from speechless.utils.logging import CommandLogEntry, CommandLogger


class TestCommandLogEntry:
    """Tests for CommandLogEntry dataclass."""

    def test_all_fields_required(self):
        entry = CommandLogEntry(
            timestamp="2024-01-01T12:00:00+00:00",
            transcription="set temperature to 22",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        assert entry.timestamp == "2024-01-01T12:00:00+00:00"
        assert entry.transcription == "set temperature to 22"
        assert entry.classification == "vehicle_control"
        assert entry.routing_decision == "edge"
        assert entry.execution_outcome == "success"
        assert entry.connectivity_state == "online"

    def test_fields_store_arbitrary_strings(self):
        entry = CommandLogEntry(
            timestamp="2024-06-15T08:30:00Z",
            transcription="what's the weather like",
            classification="informational",
            routing_decision="cloud",
            execution_outcome="error: timeout",
            connectivity_state="offline",
        )
        assert entry.execution_outcome == "error: timeout"
        assert entry.connectivity_state == "offline"


class TestCommandLogger:
    """Tests for CommandLogger class."""

    def test_empty_log_initially(self):
        logger = CommandLogger()
        assert logger.get_log() == []

    def test_log_single_command(self):
        logger = CommandLogger()
        entry = CommandLogEntry(
            timestamp="2024-01-01T12:00:00+00:00",
            transcription="open the window",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        logger.log_command(entry)
        log = logger.get_log()
        assert len(log) == 1
        assert log[0] == entry

    def test_log_multiple_commands_in_order(self):
        logger = CommandLogger()
        entries = [
            CommandLogEntry(
                timestamp=f"2024-01-01T12:0{i}:00+00:00",
                transcription=f"command {i}",
                classification="vehicle_control",
                routing_decision="edge",
                execution_outcome="success",
                connectivity_state="online",
            )
            for i in range(3)
        ]
        for entry in entries:
            logger.log_command(entry)

        log = logger.get_log()
        assert len(log) == 3
        assert log == entries

    def test_get_log_returns_copy(self):
        """Modifying the returned list should not affect internal state."""
        logger = CommandLogger()
        entry = CommandLogEntry(
            timestamp="2024-01-01T12:00:00+00:00",
            transcription="lock doors",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        logger.log_command(entry)
        log = logger.get_log()
        log.clear()
        # Internal log should be unaffected
        assert len(logger.get_log()) == 1

    def test_clear_removes_all_entries(self):
        logger = CommandLogger()
        entry = CommandLogEntry(
            timestamp="2024-01-01T12:00:00+00:00",
            transcription="turn on lights",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        logger.log_command(entry)
        logger.clear()
        assert logger.get_log() == []

    def test_create_entry_with_auto_timestamp(self):
        entry = CommandLogger.create_entry(
            transcription="find restaurants",
            classification="informational",
            routing_decision="cloud",
            execution_outcome="success",
            connectivity_state="online",
        )
        # Timestamp should be a valid ISO format string
        parsed = datetime.fromisoformat(entry.timestamp)
        assert parsed.tzinfo is not None
        assert entry.transcription == "find restaurants"
        assert entry.classification == "informational"

    def test_create_entry_with_custom_timestamp(self):
        custom_ts = "2024-06-15T10:30:00+02:00"
        entry = CommandLogger.create_entry(
            transcription="what time is it",
            classification="informational",
            routing_decision="cloud",
            execution_outcome="success",
            connectivity_state="online",
            timestamp=custom_ts,
        )
        assert entry.timestamp == custom_ts

    def test_log_entry_contains_all_required_fields(self):
        """Verify the log entry has all six required fields per requirement 5.4."""
        entry = CommandLogEntry(
            timestamp="2024-01-01T00:00:00Z",
            transcription="test",
            classification="informational",
            routing_decision="cloud",
            execution_outcome="success",
            connectivity_state="online",
        )
        required_fields = {
            "timestamp",
            "transcription",
            "classification",
            "routing_decision",
            "execution_outcome",
            "connectivity_state",
        }
        actual_fields = set(vars(entry).keys())
        assert required_fields.issubset(actual_fields)
