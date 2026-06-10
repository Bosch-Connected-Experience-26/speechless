"""Interactive dashboard command processing."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from speechless.cloud.realtime import RealTimeQueryHandler
from speechless.context.conversation import ConversationContext
from speechless.dashboard.backends import VehicleBackend
from speechless.edge.edge_llm import EdgeLLMClient, EdgeLLMConfig
from speechless.edge.intent_parser import IntentParser
from speechless.models import AppConfig
from speechless.router.classifier import CommandCategory, CommandClassifier
from speechless.utils.logging import CommandLogger


@dataclass
class InteractionStats:
    """Aggregate statistics for interactive command processing."""

    total_commands: int = 0
    edge_executions: int = 0
    cloud_executions: int = 0
    fallbacks_used: int = 0
    success_count: int = 0
    total_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_commands == 0:
            return 0.0
        return self.success_count / self.total_commands

    @property
    def avg_latency_ms(self) -> float:
        if self.total_commands == 0:
            return 0.0
        return self.total_latency_ms / self.total_commands

    def to_dict(self) -> dict:
        """Return a dashboard-friendly stats dict."""
        return {
            "total_commands": self.total_commands,
            "edge_executions": self.edge_executions,
            "cloud_executions": self.cloud_executions,
            "fallbacks_used": self.fallbacks_used,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
        }


class DashboardInteractionService:
    """Processes arbitrary interactive dashboard utterances."""

    def __init__(
        self,
        config: AppConfig,
        backend: VehicleBackend,
        *,
        conversation_context: ConversationContext | None = None,
        logger: CommandLogger | None = None,
    ) -> None:
        self.config = config
        self.backend = backend
        self.parser = IntentParser()
        self.classifier = CommandClassifier(
            confidence_threshold=config.classification_confidence_threshold
        )
        self.context = conversation_context or ConversationContext()
        self.logger = logger or CommandLogger()
        self.stats = InteractionStats()
        self._bedrock_client = None
        self._edge_llm_client: EdgeLLMClient | None = None

    async def process_text(
        self,
        text: str,
        *,
        network_status: dict | None = None,
        transcription_source: str = "text",
        transcription_confidence: float = 1.0,
    ) -> dict:
        """Process one user utterance and return dashboard state updates."""
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Command text cannot be empty")

        start = time.perf_counter()
        network = network_status or {"is_connected": True}
        is_online = bool(network.get("is_connected", True))

        classification = self.classifier.classify(cleaned)
        intent = self.parser.parse(cleaned)

        if intent is not None:
            route = "edge"
            result = await self.backend.execute_intent(intent)
            response = result["message"]
            intent_name = f"{intent.system.value}.{intent.action.value}"
            criticality = "high_priority"
            success = bool(result["success"])
            fallback_used = False
            classification_value = CommandCategory.VEHICLE_CONTROL.value
        else:
            route = "cloud" if is_online else "edge"
            if route == "cloud":
                response = self._cloud_response(cleaned)
                criticality = "normal"
                fallback_used = False
            else:
                response = self._edge_response(cleaned)
                criticality = "normal"
                fallback_used = classification.category == CommandCategory.INFORMATIONAL
            success = True
            intent_name = f"informational.{self._extract_intent_name(cleaned)}"
            classification_value = classification.category.value
            self.context.add_turn("user", cleaned)
            self.context.add_turn("assistant", response)

        latency_ms = max((time.perf_counter() - start) * 1000, 8.0 if route == "edge" else 15.0)

        self._update_stats(route, success, fallback_used, latency_ms)
        self.logger.log_command(
            transcription=cleaned,
            classification=classification_value,
            routing_decision=route,
            execution_outcome="success" if success else "error",
            connectivity_state="online" if is_online else "offline",
        )

        return {
            "current_command": {
                "raw_text": cleaned,
                "intent": intent_name,
                "confidence": min(classification.confidence, transcription_confidence),
                "criticality": criticality,
                "source": transcription_source,
            },
            "routing_decision": {
                "intent": intent_name,
                "executed_on": route,
                "latency_ms": latency_ms,
                "success": success,
                "response": response,
                "fallback_used": fallback_used,
            },
            "vehicle_state": self.backend.get_vehicle_state(),
            "statistics": self.stats.to_dict(),
            "assistant_response": response,
        }

    def reset(self) -> None:
        """Reset interactive statistics and context."""
        self.stats = InteractionStats()
        self.context.clear()
        self.logger.clear()

    def _update_stats(
        self,
        route: str,
        success: bool,
        fallback_used: bool,
        latency_ms: float,
    ) -> None:
        self.stats.total_commands += 1
        if route == "edge":
            self.stats.edge_executions += 1
        else:
            self.stats.cloud_executions += 1
        if success:
            self.stats.success_count += 1
        if fallback_used:
            self.stats.fallbacks_used += 1
        self.stats.total_latency_ms += latency_ms

    def _cloud_response(self, text: str) -> str:
        bedrock = self._get_bedrock_client()
        realtime = RealTimeQueryHandler(bedrock_client=bedrock)
        text_lower = text.lower()

        if "gas" in text_lower or "fuel" in text_lower or "price" in text_lower:
            result = realtime.query_fuel_price("Shell A9" if "shell" in text_lower else None)
            if result.success:
                return result.text

        if any(word in text_lower for word in ("food", "restaurant", "hungry", "pasta")):
            result = realtime.query_restaurant_availability(
                cuisine="Italian" if "italian" in text_lower or "pasta" in text_lower else None,
                location="nearby",
            )
            if result.success:
                return result.text

        if bedrock is not None:
            try:
                response = bedrock.converse(text)
                if response.success and response.text:
                    return response.text
            except Exception:
                pass

        return self._fallback_response(text, route="cloud")

    def _edge_response(self, text: str) -> str:
        edge = self._get_edge_llm_client()
        if edge is not None:
            messages = edge.build_request_messages(self.context.get_messages_for_llm(), text)
            response = edge.generate(messages)
            if response.success and response.text:
                return response.text
        return self._fallback_response(text, route="edge")

    def _get_bedrock_client(self):
        if not _env_enabled("SPEECHLESS_BEDROCK_ENABLED"):
            return None
        if self._bedrock_client is not None:
            return self._bedrock_client
        try:
            from speechless.cloud.bedrock_client import BedrockClient

            self._bedrock_client = BedrockClient(
                model_id=self.config.bedrock_model_id,
                region=self.config.bedrock_region,
                profile_name=self.config.bedrock_profile,
            )
            return self._bedrock_client
        except Exception:
            return None

    def _get_edge_llm_client(self) -> EdgeLLMClient | None:
        if not _env_enabled("SPEECHLESS_EDGE_LLM_ENABLED"):
            return None
        if self._edge_llm_client is not None:
            return self._edge_llm_client
        try:
            client = EdgeLLMClient(
                EdgeLLMConfig(
                    target=self.config.edge_target,
                    lmstudio_url=self.config.edge_lm_url,
                    jetson_url=self.config.jetson_url,
                    model_name=self.config.edge_model_name,
                )
            )
            if client.validate_connectivity():
                self._edge_llm_client = client
                return client
        except Exception:
            return None
        return None

    @staticmethod
    def _fallback_response(text: str, route: str) -> str:
        text_lower = text.lower()

        if route == "edge":
            if "food" in text_lower or "restaurant" in text_lower or "hungry" in text_lower:
                return "I'm offline. What type of cuisine do you prefer?"
            if "pasta" in text_lower or "seafood" in text_lower:
                return "Seafood pasta noted. I can refine the route when connectivity returns."
            return "Processing locally. I can handle vehicle controls and basic guidance offline."

        if "food" in text_lower or "restaurant" in text_lower or "hungry" in text_lower:
            return "Found nearby options: Pasta Perfetto, Golden Dragon, and Casa Taco."
        if "route" in text_lower or "navigate" in text_lower:
            return "Route calculated. ETA is 18 minutes via A9 highway."
        if "gas" in text_lower or "fuel" in text_lower or "price" in text_lower:
            return "Shell A9 is estimated at 2.35 EUR/L. Live price data is not connected."
        if "weather" in text_lower:
            return "Currently 22 C and partly cloudy. No rain is expected today."
        return f"Processed query: {text}"

    @staticmethod
    def _extract_intent_name(text: str) -> str:
        text_lower = text.lower()
        if "food" in text_lower or "restaurant" in text_lower or "hungry" in text_lower:
            return "food_search"
        if "route" in text_lower or "navigate" in text_lower:
            return "navigation"
        if "gas" in text_lower or "fuel" in text_lower or "price" in text_lower:
            return "fuel_price"
        if "weather" in text_lower:
            return "weather"
        return "general_query"


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
