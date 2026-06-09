"""Tests for the structured logging utility module."""

from datetime import datetime, timezone

import pytest

from speechless.utils.logging import CommandLogEntry, CommandLogger


class TestCommandLogEntry:
    """Tests for CommandLogEntry dataclass."""

    def test_all_required_fields_present(self):
        entry = CommandLogEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            transcription="set temperature to 22",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        assert entry.timestamp == "2024-01-01T00:00:00+00:00"
        assert entry.transcription == "set temperature to 22"
        assert entry.classification == "vehicle_control"
        assert entry.routing_decision == "edge"
        assert entry.execution_outcome == "success"
        assert entry.connectivity_state == "online"
        assert entry.error_detail is None

    def test_optional_error_detail(self):
        entry = CommandLogEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            transcription="lock doors",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="error",
            connectivity_state="online",
            error_detail="Kuksa connection timeout",
        )
        assert entry.error_detail == "Kuksa connection timeout"


class TestCommandLogger:
    """Tests for CommandLogger class."""

    def test_log_command_returns_entry(self):
        logger = CommandLogger()
        entry = logger.log_command(
            transcription="open windows",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        assert isinstance(entry, CommandLogEntry)
        assert entry.transcription == "open windows"

    def test_log_command_generates_iso_timestamp(self):
        logger = CommandLogger()
        entry = logger.log_command(
            transcription="what is the weather",
            classification="informational",
            routing_decision="cloud",
            execution_outcome="success",
        )
        # Should parse as valid ISO format
        parsed = datetime.fromisoformat(entry.timestamp)
        assert parsed.tzinfo is not None

    def test_log_command_default_connectivity_state(self):
        logger = CommandLogger()
        entry = logger.log_command(
            transcription="turn on lights",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
        )
        assert entry.connectivity_state == "online"

    def test_log_command_offline_state(self):
        logger = CommandLogger()
        entry = logger.log_command(
            transcription="find restaurant",
            classification="informational",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="offline",
        )
        assert entry.connectivity_state == "offline"

    def test_get_history_returns_all_entries(self):
        logger = CommandLogger()
        logger.log_command(
            transcription="command 1",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
        )
        logger.log_command(
            transcription="command 2",
            classification="informational",
            routing_decision="cloud",
            execution_outcome="success",
        )
        history = logger.get_history()
        assert len(history) == 2
        assert history[0].transcription == "command 1"
        assert history[1].transcription == "command 2"

    def test_get_history_returns_copy(self):
        logger = CommandLogger()
        logger.log_command(
            transcription="test",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
        )
        history = logger.get_history()
        history.clear()
        # Original history should not be affected
        assert len(logger.get_history()) == 1

    def test_clear_removes_all_entries(self):
        logger = CommandLogger()
        logger.log_command(
            transcription="command 1",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
        )
        logger.log_command(
            transcription="command 2",
            classification="informational",
            routing_decision="cloud",
            execution_outcome="success",
        )
        assert len(logger.get_history()) == 2
        logger.clear()
        assert len(logger.get_history()) == 0

    def test_clear_allows_new_entries(self):
        logger = CommandLogger()
        logger.log_command(
            transcription="old command",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
        )
        logger.clear()
        logger.log_command(
            transcription="new command",
            classification="informational",
            routing_decision="cloud",
            execution_outcome="success",
        )
        history = logger.get_history()
        assert len(history) == 1
        assert history[0].transcription == "new command"

    def test_validate_entry_valid(self):
        entry = CommandLogEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            transcription="lock doors",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        assert CommandLogger.validate_entry(entry) is True

    def test_validate_entry_invalid_classification(self):
        entry = CommandLogEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            transcription="lock doors",
            classification="unknown",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        assert CommandLogger.validate_entry(entry) is False

    def test_validate_entry_invalid_routing(self):
        entry = CommandLogEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            transcription="lock doors",
            classification="vehicle_control",
            routing_decision="invalid",
            execution_outcome="success",
            connectivity_state="online",
        )
        assert CommandLogger.validate_entry(entry) is False

    def test_validate_entry_invalid_outcome(self):
        entry = CommandLogEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            transcription="lock doors",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="unknown",
            connectivity_state="online",
        )
        assert CommandLogger.validate_entry(entry) is False

    def test_validate_entry_invalid_connectivity(self):
        entry = CommandLogEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            transcription="lock doors",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="disconnected",
        )
        assert CommandLogger.validate_entry(entry) is False

    def test_validate_entry_empty_timestamp(self):
        entry = CommandLogEntry(
            timestamp="",
            transcription="lock doors",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        assert CommandLogger.validate_entry(entry) is False

    def test_validate_entry_empty_transcription(self):
        entry = CommandLogEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            transcription="",
            classification="vehicle_control",
            routing_decision="edge",
            execution_outcome="success",
            connectivity_state="online",
        )
        assert CommandLogger.validate_entry(entry) is False
