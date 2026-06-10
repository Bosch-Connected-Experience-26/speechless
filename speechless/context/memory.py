"""MongoDB-backed persistent memory for the voice assistant.

Inspired by Amazon Bedrock AgentCore Memory's dual-level approach:
    - Short-term memory: Session-based conversation context (per-trip)
    - Long-term memory: Driver preferences and facts persisted across sessions

Data is stored locally in MongoDB, enabling:
    - Offline persistence (no cloud dependency for memory)
    - Sync-when-online: accumulated context can be forwarded to Bedrock
    - Cross-session personalization (food preferences, route history, etc.)

Collections:
    - sessions: Active and historical conversation sessions
    - preferences: Extracted driver preferences (auto-updated from interactions)
    - command_log: Full audit trail of every processed command
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


class MemoryStore:
    """MongoDB-backed persistent memory for driver context and preferences.

    Provides auto-save/retrieve hooks that the pipeline orchestrator calls
    on each interaction — the driver never needs to think about memory.

    Args:
        mongo_uri: MongoDB connection string.
        database_name: Database name (default: "speechless").
        driver_id: Identifier for the current driver (default: "default").
    """

    def __init__(
        self,
        mongo_uri: str = "mongodb://localhost:27017",
        database_name: str = "speechless",
        driver_id: str = "default",
    ):
        self._client: MongoClient = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        self._db: Database = self._client[database_name]
        self._driver_id = driver_id

        # Collections
        self._sessions: Collection = self._db["sessions"]
        self._preferences: Collection = self._db["preferences"]
        self._command_log: Collection = self._db["command_log"]

        # Ensure indexes
        self._sessions.create_index([("driver_id", 1), ("session_id", 1)])
        self._sessions.create_index([("driver_id", 1), ("is_active", 1)])
        self._preferences.create_index([("driver_id", 1), ("key", 1)], unique=True)
        self._command_log.create_index([("driver_id", 1), ("timestamp", -1)])

    @property
    def db(self) -> Database:
        """Direct access to the database for advanced queries."""
        return self._db

    # ── Short-term memory (session context) ──────────────────────────────

    def save_session(
        self, session_id: str, turns: list[dict], is_active: bool = True
    ) -> None:
        """Persist or update a conversation session.

        Called automatically after each interaction (AgentCore hook pattern).
        """
        self._sessions.update_one(
            {"driver_id": self._driver_id, "session_id": session_id},
            {
                "$set": {
                    "turns": turns,
                    "is_active": is_active,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )

    def load_session(self, session_id: str) -> Optional[list[dict]]:
        """Load a conversation session by ID. Returns None if not found."""
        doc = self._sessions.find_one(
            {"driver_id": self._driver_id, "session_id": session_id}
        )
        return doc["turns"] if doc else None

    def get_active_session(self) -> Optional[dict]:
        """Get the most recent active session for this driver."""
        return self._sessions.find_one(
            {"driver_id": self._driver_id, "is_active": True},
            sort=[("updated_at", -1)],
        )

    def close_session(self, session_id: str) -> None:
        """Mark a session as inactive (trip ended)."""
        self._sessions.update_one(
            {"driver_id": self._driver_id, "session_id": session_id},
            {"$set": {"is_active": False, "closed_at": datetime.now(timezone.utc)}},
        )

    # ── Long-term memory (driver preferences) ────────────────────────────

    def save_preference(self, key: str, value: Any, source: str = "inferred") -> None:
        """Save or update a driver preference.

        Examples:
            save_preference("food_cuisine", "Italian", source="explicit")
            save_preference("preferred_fuel_brand", "Shell", source="inferred")
        """
        self._preferences.update_one(
            {"driver_id": self._driver_id, "key": key},
            {
                "$set": {
                    "value": value,
                    "source": source,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )

    def get_preference(self, key: str) -> Optional[Any]:
        """Retrieve a specific driver preference."""
        doc = self._preferences.find_one(
            {"driver_id": self._driver_id, "key": key}
        )
        return doc["value"] if doc else None

    def get_all_preferences(self) -> dict[str, Any]:
        """Retrieve all preferences for the current driver."""
        docs = self._preferences.find({"driver_id": self._driver_id})
        return {doc["key"]: doc["value"] for doc in docs}

    def delete_preference(self, key: str) -> None:
        """Remove a specific preference."""
        self._preferences.delete_one({"driver_id": self._driver_id, "key": key})

    # ── Command log (audit trail) ────────────────────────────────────────

    def log_command(
        self,
        transcription: str,
        classification: str,
        routing: str,
        outcome: str,
        connectivity_state: str,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Log a processed command for debugging and analytics.

        Every command passing through the pipeline gets logged here,
        satisfying the structured logging requirement (Req 5.4).
        """
        entry = {
            "driver_id": self._driver_id,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc),
            "transcription": transcription,
            "classification": classification,
            "routing": routing,
            "outcome": outcome,
            "connectivity_state": connectivity_state,
        }
        if metadata:
            entry["metadata"] = metadata
        self._command_log.insert_one(entry)

    def get_recent_commands(self, limit: int = 20) -> list[dict]:
        """Retrieve recent command log entries for this driver."""
        cursor = self._command_log.find(
            {"driver_id": self._driver_id},
            sort=[("timestamp", -1)],
            limit=limit,
        )
        return list(cursor)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Check MongoDB connectivity. Returns True if reachable."""
        try:
            self._client.admin.command("ping")
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close the MongoDB connection."""
        self._client.close()
