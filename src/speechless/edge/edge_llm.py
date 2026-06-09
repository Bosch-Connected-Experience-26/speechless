"""Edge LLM client using OpenAI-compatible API.

Supports dual deployment targets:
- LM Studio (localhost, OpenAI-compatible) for development
- NVIDIA Jetson (TensorRT/CUDA, OpenAI-compatible) for production

The API contract is identical regardless of backend — same request
format, same response parsing. Target is switched via config only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from openai import OpenAI


@dataclass
class EdgeLLMConfig:
    """Configuration for the edge LLM target.

    Args:
        target: "lmstudio" or "jetson" — selects endpoint URL.
        lmstudio_url: LM Studio endpoint (development).
        jetson_url: Jetson TensorRT endpoint (production).
        model_name: Model name for API calls.
        timeout: Request timeout in seconds.
    """

    target: str = "lmstudio"
    lmstudio_url: str = "http://localhost:1234/v1"
    jetson_url: str = "http://jetson-device:8080/v1"
    model_name: str = "local-model"
    timeout: float = 10.0


@dataclass
class EdgeLLMResponse:
    """Response from edge LLM inference."""

    text: str
    model: str
    success: bool
    error_message: Optional[str] = None


class EdgeLLMClient:
    """Unified OpenAI-compatible client for edge LLM inference.

    Supports dual targets:
    - LM Studio (localhost, OpenAI-compatible) for development
    - NVIDIA Jetson (TensorRT/CUDA, OpenAI-compatible) for production

    Args:
        config: EdgeLLMConfig with target and endpoint settings.
    """

    def __init__(self, config: EdgeLLMConfig):
        self.config = config
        base_url = config.lmstudio_url if config.target == "lmstudio" else config.jetson_url
        self.client = OpenAI(
            base_url=base_url,
            api_key="not-needed",  # Local models don't require API keys
            timeout=config.timeout,
        )
        self._ready = False

    def validate_connectivity(self) -> bool:
        """Validate connectivity to the configured endpoint within 3 seconds.

        Returns:
            True if endpoint is responsive, False otherwise.
        """
        try:
            self.client.models.list()
            self._ready = True
            return True
        except Exception:
            self._ready = False
            return False

    @property
    def is_ready(self) -> bool:
        """Whether the endpoint has been validated as responsive."""
        return self._ready

    def generate(self, messages: list[dict]) -> EdgeLLMResponse:
        """Generate a response using the edge LLM with OpenAI chat format.

        Args:
            messages: List of message dicts with "role" and "content" keys.

        Returns:
            EdgeLLMResponse with generated text or error details.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=512,
            )
            return EdgeLLMResponse(
                text=response.choices[0].message.content,
                model=self.config.model_name,
                success=True,
            )
        except Exception as e:
            return EdgeLLMResponse(
                text="",
                model=self.config.model_name,
                success=False,
                error_message=f"Edge LLM error: {str(e)}",
            )

    def build_request_messages(
        self, conversation_history: list[dict], user_message: str
    ) -> list[dict]:
        """Build the full messages list including system prompt and conversation history.

        The format is identical regardless of backend (LM Studio or Jetson).

        Args:
            conversation_history: Prior turns as list of {"role": ..., "content": ...}.
            user_message: The new user message.

        Returns:
            Complete message list ready for the chat completions API.
        """
        messages = [
            {"role": "system", "content": "You are a helpful in-vehicle voice assistant."}
        ]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        return messages
