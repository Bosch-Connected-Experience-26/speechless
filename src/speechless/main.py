"""Pipeline orchestrator and main entry point.

Wires all components together and implements the state machine:
IDLE → LISTENING → TRANSCRIBING → CLASSIFYING → EXECUTING → RESPONDING

Handles mode-aware routing (ONLINE/OFFLINE) and integrates with
the Connectivity Monitor and Biometric Monitor via callbacks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from speechless.connectivity.monitor import ConnectivityMonitor, ConnectivityState
from speechless.context.conversation import ConversationContext
from speechless.models import AppConfig, PipelineContext, PipelineState, ProcessingMode
from speechless.router.classifier import CommandClassifier, CommandCategory
from speechless.utils.logging import CommandLogEntry, CommandLogger


class PipelineOrchestrator:
    """Main pipeline orchestrator for the voice assistant.

    Manages the processing pipeline state machine and routes commands
    between edge and cloud based on connectivity and classification.

    Args:
        config: Application configuration.
        classifier: Command classifier instance.
        logger: Structured command logger.
        connectivity_monitor: Connectivity state monitor.
        conversation_context: Conversation context for offline history.
    """

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        classifier: Optional[CommandClassifier] = None,
        logger: Optional[CommandLogger] = None,
        connectivity_monitor: Optional[ConnectivityMonitor] = None,
        conversation_context: Optional[ConversationContext] = None,
    ):
        self.config = config or AppConfig()
        self.classifier = classifier or CommandClassifier(
            confidence_threshold=self.config.classification_confidence_threshold
        )
        self.logger = logger or CommandLogger()
        self.connectivity_monitor = connectivity_monitor
        self.conversation_context = conversation_context or ConversationContext()
        self._pipeline_context = PipelineContext()

    @property
    def state(self) -> PipelineState:
        """Current pipeline state."""
        return self._pipeline_context.state

    @property
    def mode(self) -> ProcessingMode:
        """Current processing mode (ONLINE/OFFLINE)."""
        return self._pipeline_context.mode

    def transition_state(self, new_state: PipelineState) -> None:
        """Transition pipeline to a new state."""
        self._pipeline_context.state = new_state

    def handle_connectivity_change(self, new_state: ConnectivityState) -> None:
        """Handle connectivity state change callback.

        Switches between ONLINE and OFFLINE processing modes.
        On reconnection (OFFLINE → ONLINE), context can be forwarded to cloud.
        """
        if new_state == ConnectivityState.ONLINE:
            self._pipeline_context.mode = ProcessingMode.ONLINE
        else:
            self._pipeline_context.mode = ProcessingMode.OFFLINE

    def determine_route(self, classification_category: CommandCategory) -> str:
        """Determine routing based on classification and connectivity.

        Routing logic:
        - ONLINE + VEHICLE_CONTROL → "edge"
        - ONLINE + INFORMATIONAL → "cloud"
        - OFFLINE + any → "edge" (Edge LLM handles everything)

        Args:
            classification_category: The classified command category.

        Returns:
            "edge" or "cloud" routing destination.
        """
        if self._pipeline_context.mode == ProcessingMode.OFFLINE:
            return "edge"

        if classification_category == CommandCategory.VEHICLE_CONTROL:
            return "edge"
        return "cloud"

    async def process_command(self, transcription: str) -> str:
        """Process a transcribed command through the full pipeline.

        Args:
            transcription: Text from the speech engine.

        Returns:
            Response text from the executed command.
        """
        self._pipeline_context.start_time = datetime.now(timezone.utc)

        try:
            # CLASSIFYING
            self.transition_state(PipelineState.CLASSIFYING)
            classification = self.classifier.classify(transcription)
            route = self.determine_route(classification.category)

            # EXECUTING
            self.transition_state(PipelineState.EXECUTING)
            self._pipeline_context.classification = classification.category.value
            self._pipeline_context.routing = route

            # Execute based on route (actual execution delegated to edge/cloud)
            response_text = f"Processed: {transcription} (route={route})"

            # RESPONDING
            self.transition_state(PipelineState.RESPONDING)
            self._pipeline_context.response_text = response_text

            # Log the command
            self.logger.log_command(
                transcription=transcription,
                classification=classification.category.value,
                routing_decision=route,
                execution_outcome="success",
                connectivity_state=self._pipeline_context.mode.value,
            )

            # Return to IDLE
            self.transition_state(PipelineState.IDLE)
            return response_text

        except Exception as e:
            # Error recovery: notify and reset to IDLE
            self._pipeline_context.error = str(e)
            self.logger.log_command(
                transcription=transcription,
                classification=self._pipeline_context.classification or "unknown",
                routing_decision=self._pipeline_context.routing or "unknown",
                execution_outcome="error",
                connectivity_state=self._pipeline_context.mode.value,
                error_detail=str(e),
            )
            self.transition_state(PipelineState.IDLE)
            return f"Error: {str(e)}"

    def reset(self) -> None:
        """Reset the pipeline to initial state."""
        self._pipeline_context = PipelineContext()
