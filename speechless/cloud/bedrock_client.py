"""AWS Bedrock client using the converse API.

Authenticated via the "losrudos" AWS CLI profile. Supports multi-turn
conversations and context injection for offline-to-online forwarding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig


@dataclass
class BedrockResponse:
    """Response from AWS Bedrock converse API."""

    text: str
    model: str
    success: bool
    error_message: Optional[str] = None


@dataclass
class ConversationMessage:
    """A single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str


class BedrockClient:
    """AWS Bedrock client using the converse API with profile 'losrudos'.

    Args:
        model_id: Bedrock model identifier.
        region: AWS region for Bedrock.
        timeout: Request timeout in seconds.
        profile_name: AWS CLI profile name for authentication.
    """

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
        region: str = "us-east-1",
        timeout: float = 5.0,
        profile_name: str = "losrudos",
    ):
        self.model_id = model_id
        self.timeout = timeout
        self.profile_name = profile_name
        session = boto3.Session(profile_name=profile_name)
        self.client = session.client(
            "bedrock-runtime",
            region_name=region,
            config=BotoConfig(
                read_timeout=int(timeout),
                connect_timeout=3,
            ),
        )
        self._injected_context: list[ConversationMessage] = []

    def converse(
        self,
        user_message: str,
        history: Optional[list[ConversationMessage]] = None,
    ) -> BedrockResponse:
        """Send a message to Bedrock using the converse API.

        Args:
            user_message: The new user query.
            history: Optional conversation history for multi-turn.

        Returns:
            BedrockResponse with the model's reply.
        """
        messages = self._build_messages(user_message, history)

        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=messages,
            )
            # Extract text from Bedrock converse response
            output = response.get("output", {})
            message = output.get("message", {})
            content_blocks = message.get("content", [])
            text = ""
            for block in content_blocks:
                if "text" in block:
                    text += block["text"]

            return BedrockResponse(
                text=text,
                model=self.model_id,
                success=True,
            )
        except Exception as e:
            error_type = type(e).__name__
            return BedrockResponse(
                text="",
                model=self.model_id,
                success=False,
                error_message=f"Bedrock error ({error_type}): {str(e)}",
            )

    def inject_context(self, context: list[ConversationMessage]) -> None:
        """Inject offline conversation context for the next converse call.

        Used when transitioning from offline to online — the accumulated
        offline turns are forwarded to Bedrock for enriched responses.

        Args:
            context: List of ConversationMessages accumulated offline.
        """
        self._injected_context = list(context)

    def _build_messages(
        self,
        user_message: str,
        history: Optional[list[ConversationMessage]] = None,
    ) -> list[dict]:
        """Build the messages list for the Bedrock converse API.

        Includes injected context (from offline forwarding) + explicit history
        + new user message, in chronological order.

        Args:
            user_message: The new user message.
            history: Explicit conversation history.

        Returns:
            List of message dicts formatted for Bedrock converse API.
        """
        messages: list[dict] = []

        # First: injected offline context
        for msg in self._injected_context:
            messages.append({
                "role": msg.role,
                "content": [{"text": msg.content}],
            })

        # Then: explicit history
        if history:
            for msg in history:
                messages.append({
                    "role": msg.role,
                    "content": [{"text": msg.content}],
                })

        # Finally: new user message
        messages.append({
            "role": "user",
            "content": [{"text": user_message}],
        })

        return messages

    def clear_injected_context(self) -> None:
        """Clear any previously injected offline context."""
        self._injected_context.clear()
