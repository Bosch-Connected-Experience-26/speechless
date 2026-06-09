"""Offline conversation context manager.

Maintains multi-turn conversation history during offline sessions.
When connectivity is restored, the accumulated context is forwarded
to AWS Bedrock for enriched cloud responses.

Supports a minimum of 5 consecutive follow-up turns per session
(design requirement), with a configurable max_turns cap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ConversationTurn:
    """A single turn in a conversation (user or assistant message)."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationContext:
    """Manages multi-turn conversation context for offline interactions.

    Accumulates user/assistant turns and provides formatted message lists
    compatible with both the OpenAI-format Edge LLM and the Bedrock converse API.

    Args:
        max_turns: Maximum number of turns to retain (oldest trimmed first).
        session_id: Optional session identifier for persistence.
    """

    def __init__(self, max_turns: int = 20, session_id: str | None = None):
        self.max_turns = max_turns
        self.session_id = session_id
        self._turns: list[ConversationTurn] = []

    @property
    def turns(self) -> list[ConversationTurn]:
        """All stored conversation turns."""
        return list(self._turns)

    @property
    def turn_count(self) -> int:
        """Number of turns currently stored."""
        return len(self._turns)

    def add_turn(self, role: str, content: str) -> None:
        """Add a conversation turn, trimming oldest if over max_turns.

        Args:
            role: "user" or "assistant"
            content: The message text.
        """
        self._turns.append(ConversationTurn(role=role, content=content))
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns:]

    def get_messages_for_llm(self) -> list[dict[str, str]]:
        """Format turns for OpenAI-compatible chat completions API.

        Returns:
            List of {"role": ..., "content": ...} dicts.
        """
        return [{"role": t.role, "content": t.content} for t in self._turns]

    def get_messages_for_bedrock(self) -> list[dict[str, str]]:
        """Format turns for AWS Bedrock converse API.

        Returns:
            List of {"role": ..., "content": ...} dicts in Bedrock format.
        """
        return [{"role": t.role, "content": t.content} for t in self._turns]

    def clear(self) -> None:
        """Clear all conversation turns."""
        self._turns.clear()

    def is_empty(self) -> bool:
        """Check if context has no turns."""
        return len(self._turns) == 0

    def to_dict_list(self) -> list[dict]:
        """Serialize turns for persistence (MongoDB storage)."""
        return [
            {
                "role": t.role,
                "content": t.content,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in self._turns
        ]

    @classmethod
    def from_dict_list(
        cls, data: list[dict], max_turns: int = 20, session_id: str | None = None
    ) -> "ConversationContext":
        """Reconstruct context from persisted data."""
        ctx = cls(max_turns=max_turns, session_id=session_id)
        for item in data:
            turn = ConversationTurn(
                role=item["role"],
                content=item["content"],
                timestamp=datetime.fromisoformat(item["timestamp"])
                if "timestamp" in item
                else datetime.now(timezone.utc),
            )
            ctx._turns.append(turn)
        return ctx
