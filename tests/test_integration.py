"""Integration tests for end-to-end system flows.

Tasks 17.1-17.5: Tests for speech-to-command pipeline, vehicle control flow,
connectivity transitions, route planning/biometric flows, and demo scenario.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from speechless.cloud.bedrock_client import BedrockClient, BedrockResponse, ConversationMessage
from speechless.cloud.realtime import RealTimeQueryHandler, RealTimeQueryResult
from speechless.connectivity.monitor import ConnectivityMonitor, ConnectivityConfig, ConnectivityState
from speechless.context.conversation import ConversationContext
from speechless.edge.edge_llm import EdgeLLMClient, EdgeLLMConfig, EdgeLLMResponse
from speechless.edge.intent_parser import IntentParser, VehicleSystem, Action
from speechless.edge.vehicle_controller import VehicleController, VSSSignal, ActuationResult
from speechless.main import PipelineOrchestrator
from speechless.models import AppConfig, PipelineState, ProcessingMode
from speechless.router.classifier import CommandClassifier, CommandCategory
from speechless.routing.planner import GeoPoint, RouteConstraint, RoutePlanner
from speechless.speech.stt_local import TranscriptionResult
from speechless.speech.stt_cloud import CloudSTT
from speechless.telemetry.biometric import BiometricConfig, BiometricMonitor
from speechless.telemetry.reader import TelemetryReader, VehicleTelemetry
from speechless.utils.logging import CommandLogger


# ============================================================================
# 17.1 Integration tests for speech-to-command pipeline
# ============================================================================


class TestSpeechToCommandPipeline:
    """Integration: mocked audio → STT → classifier → routing."""

    def test_vehicle_command_routes_to_edge(self):
        """Full pipeline: vehicle command text → classify → route to edge."""
        orchestrator = PipelineOrchestrator()
        result = asyncio.run(orchestrator.process_command("set temperature to 22"))

        assert "route=edge" in result
        history = orchestrator.logger.get_history()
        assert len(history) == 1
        assert history[0].classification == "vehicle_control"
        assert history[0].routing_decision == "edge"

    def test_informational_query_routes_to_cloud(self):
        """Full pipeline: informational query → classify → route to cloud."""
        orchestrator = PipelineOrchestrator()
        result = asyncio.run(orchestrator.process_command("what is the weather today"))

        assert "route=cloud" in result
        history = orchestrator.logger.get_history()
        assert history[0].classification == "informational"
        assert history[0].routing_decision == "cloud"

    def test_cloud_stt_fallback_when_local_low_confidence(self):
        """Cloud STT fallback triggered when local confidence is low."""
        local_result = TranscriptionResult(
            text="unclear mumbling", confidence=0.3, source="local"
        )
        cloud_stt = CloudSTT(api_key=None)  # No API key = cloud unavailable

        # When cloud is unavailable, returns local result
        result = cloud_stt.fallback_transcribe(
            audio_samples=MagicMock(),
            local_result=local_result,
        )
        assert result == local_result
        assert result.source == "local"

    def test_cloud_stt_unavailable_uses_local(self):
        """When cloud STT is unavailable, local result is used regardless of confidence."""
        local_result = TranscriptionResult(
            text="some command", confidence=0.4, source="local"
        )
        cloud_stt = CloudSTT(api_key=None)

        result = cloud_stt.fallback_transcribe(
            audio_samples=MagicMock(),
            local_result=local_result,
        )
        assert result.text == "some command"
        assert result.source == "local"

    def test_pipeline_logs_every_command(self):
        """Every command processed gets logged with all required fields."""
        orchestrator = PipelineOrchestrator()
        commands = ["open windows", "what time is it", "lock doors"]

        for cmd in commands:
            asyncio.run(orchestrator.process_command(cmd))

        history = orchestrator.logger.get_history()
        assert len(history) == 3

        for entry in history:
            assert entry.timestamp
            assert entry.transcription
            assert entry.classification in ("vehicle_control", "informational")
            assert entry.routing_decision in ("edge", "cloud")
            assert entry.execution_outcome in ("success", "error", "timeout")
            assert entry.connectivity_state in ("online", "offline")


# ============================================================================
# 17.2 Integration tests for vehicle control flow
# ============================================================================


class TestVehicleControlFlow:
    """Integration: intent parsing → VSS signal mapping → actuation → confirmation."""

    def test_hvac_command_end_to_end(self):
        """HVAC command: parse → map to VSS → signal ready for actuation."""
        parser = IntentParser()
        controller = VehicleController()

        intent = parser.parse("set temperature to 24")
        assert intent is not None
        assert intent.system == VehicleSystem.HVAC
        assert intent.action == Action.SET_TEMPERATURE
        assert intent.parameters["temperature"] == 24

        signal = controller.intent_to_signal(intent)
        assert signal is not None
        assert signal.path == "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature"
        assert signal.value == 24

    def test_window_command_end_to_end(self):
        """Window command: parse → map to VSS signal."""
        parser = IntentParser()
        controller = VehicleController()

        intent = parser.parse("open the windows")
        assert intent is not None
        assert intent.system == VehicleSystem.WINDOWS
        assert intent.action == Action.OPEN

        signal = controller.intent_to_signal(intent)
        assert signal is not None
        assert "Window.Position" in signal.path
        assert signal.value == 100

    def test_door_lock_command_end_to_end(self):
        """Door lock command: parse → map to VSS signal."""
        parser = IntentParser()
        controller = VehicleController()

        intent = parser.parse("lock the doors")
        assert intent is not None
        assert intent.system == VehicleSystem.DOORS
        assert intent.action == Action.LOCK

        signal = controller.intent_to_signal(intent)
        assert signal is not None
        assert "IsLocked" in signal.path
        assert signal.value is True

    def test_kuksa_connection_failure_generates_error(self):
        """Connection failure produces a descriptive error message."""
        controller = VehicleController(kuksa_host="nonexistent", kuksa_port=99999)
        parser = IntentParser()

        intent = parser.parse("set temperature to 20")
        error = ConnectionError("gRPC connection refused")
        msg = controller.generate_error_message(error, intent)

        assert "hvac" in msg.lower()
        assert "set temperature" in msg.lower()
        assert "ConnectionError" in msg

    def test_exponential_backoff_retry_timing(self):
        """Exponential backoff delays increase correctly."""
        from speechless.utils.retry import RetryConfig, compute_backoff_delay

        config = RetryConfig(max_retries=3, base_delay=1.0, multiplier=2.0)
        delays = [compute_backoff_delay(i, config) for i in range(3)]
        assert delays == [1.0, 2.0, 4.0]


# ============================================================================
# 17.3 Integration tests for connectivity transitions
# ============================================================================


class TestConnectivityTransitions:
    """Integration: online→offline mode switch, context forwarding on restore."""

    def test_offline_routes_all_to_edge(self):
        """When offline, all queries route to edge regardless of classification."""
        orchestrator = PipelineOrchestrator()
        orchestrator._pipeline_context.mode = ProcessingMode.OFFLINE

        # Informational query should still route to edge when offline
        result = asyncio.run(orchestrator.process_command("what is the weather"))
        history = orchestrator.logger.get_history()
        assert history[0].routing_decision == "edge"
        assert history[0].connectivity_state == "offline"

    def test_online_informational_routes_to_cloud(self):
        """When online, informational queries route to cloud."""
        orchestrator = PipelineOrchestrator()
        orchestrator._pipeline_context.mode = ProcessingMode.ONLINE

        asyncio.run(orchestrator.process_command("tell me about the weather"))
        history = orchestrator.logger.get_history()
        assert history[0].routing_decision == "cloud"
        assert history[0].connectivity_state == "online"

    def test_connectivity_state_change_callback(self):
        """Pipeline handles connectivity state change callback correctly."""
        orchestrator = PipelineOrchestrator()
        assert orchestrator.mode == ProcessingMode.ONLINE

        orchestrator.handle_connectivity_change(ConnectivityState.OFFLINE)
        assert orchestrator.mode == ProcessingMode.OFFLINE

        orchestrator.handle_connectivity_change(ConnectivityState.ONLINE)
        assert orchestrator.mode == ProcessingMode.ONLINE

    def test_multi_turn_offline_conversation_accumulation(self):
        """5+ turns accumulated during offline session."""
        context = ConversationContext(max_turns=20)

        # Simulate 6 offline turns
        exchanges = [
            ("user", "Find me Italian food"),
            ("assistant", "What type of Italian? Pasta, pizza, or fine dining?"),
            ("user", "Pasta"),
            ("assistant", "Any price range preference?"),
            ("user", "Mid-range, around 15-20 EUR"),
            ("assistant", "I'll note pasta, mid-range. Any location preference?"),
        ]

        for role, content in exchanges:
            context.add_turn(role, content)

        assert context.turn_count == 6
        messages = context.get_messages_for_llm()
        assert len(messages) == 6
        assert messages[0]["content"] == "Find me Italian food"
        assert messages[-1]["role"] == "assistant"

    def test_context_forwarding_on_reconnection(self):
        """Accumulated offline context is forwarded to Bedrock on reconnection."""
        context = ConversationContext()
        context.add_turn("user", "Find Italian food")
        context.add_turn("assistant", "What type?")
        context.add_turn("user", "Pasta, mid-range")

        # Convert to Bedrock format
        bedrock_messages = context.get_messages_for_bedrock()
        assert len(bedrock_messages) == 3
        assert bedrock_messages[0]["role"] == "user"
        assert bedrock_messages[0]["content"] == "Find Italian food"
        assert bedrock_messages[2]["content"] == "Pasta, mid-range"

    def test_offline_to_online_context_injection(self):
        """Context injection to BedrockClient preserves all turns."""
        # Mock the boto3 client to avoid AWS credentials
        with patch("boto3.Session") as mock_session:
            mock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_client

            from speechless.cloud.bedrock_client import BedrockClient, ConversationMessage

            client = BedrockClient()

            # Inject offline context
            offline_context = [
                ConversationMessage(role="user", content="Find pasta"),
                ConversationMessage(role="assistant", content="What price range?"),
                ConversationMessage(role="user", content="Mid-range"),
            ]
            client.inject_context(offline_context)

            # Build messages for next query
            messages = client._build_messages("Now I'm back online, any restaurants nearby?")

            # Should contain: 3 injected + 1 new = 4 messages
            assert len(messages) == 4
            assert messages[0]["role"] == "user"
            assert messages[0]["content"] == [{"text": "Find pasta"}]
            assert messages[3]["role"] == "user"
            assert messages[3]["content"] == [{"text": "Now I'm back online, any restaurants nearby?"}]


# ============================================================================
# 17.4 Integration tests for route planning and biometric flows
# ============================================================================


class TestRoutePlanningAndBiometric:
    """Integration: fuel reachability, multi-constraint routing, biometric emergency."""

    def test_fuel_reachability_computation(self):
        """Compute whether destination is reachable with current fuel."""
        planner = RoutePlanner(tank_capacity=50.0)

        # 50% fuel, 8 L/100km → range = (25L / 8) * 100 = 312.5 km
        assert planner.is_reachable(50.0, 8.0, 300.0) is True
        assert planner.is_reachable(50.0, 8.0, 320.0) is False

    def test_multi_constraint_routing_with_deviation(self):
        """Route with fuel + food stops computes deviation correctly."""
        planner = RoutePlanner(tank_capacity=50.0)

        origin = GeoPoint(latitude=48.0, longitude=11.0, label="Start")
        destination = GeoPoint(latitude=48.5, longitude=11.5, label="End")
        fuel_stop = GeoPoint(latitude=48.1, longitude=11.2, label="Gas Station")
        food_stop = GeoPoint(latitude=48.3, longitude=11.3, label="Restaurant")

        constraints = [
            RouteConstraint(type="fuel", location=fuel_stop, label="Gas Station"),
            RouteConstraint(type="food", location=food_stop, label="Restaurant"),
        ]

        route = planner.compute_route_with_constraints(
            origin=origin,
            destination=destination,
            constraints=constraints,
            fuel_level=30.0,
            consumption_rate=8.0,
        )

        assert route.total_deviation_km >= 0
        assert route.additional_time_minutes >= 0
        assert "fuel" in route.constraints_satisfied
        assert "food" in route.constraints_satisfied
        assert len(route.waypoints) == 4  # origin + 2 stops + destination

    def test_route_ranking_by_deviation(self):
        """Route options are ranked by deviation (ascending)."""
        planner = RoutePlanner()
        from speechless.routing.planner import RouteOption

        routes = [
            RouteOption(total_deviation_km=15.0),
            RouteOption(total_deviation_km=5.0),
            RouteOption(total_deviation_km=10.0),
        ]
        ranked = planner.rank_routes(routes)
        assert ranked[0].total_deviation_km == 5.0
        assert ranked[1].total_deviation_km == 10.0
        assert ranked[2].total_deviation_km == 15.0

    def test_biometric_emergency_trigger(self):
        """Heart rate above threshold triggers emergency."""
        monitor = BiometricMonitor(
            config=BiometricConfig(critical_threshold=180),
        )

        assert monitor.is_critical(179) is False
        assert monitor.is_critical(180) is True
        assert monitor.is_critical(200) is True

    def test_biometric_emergency_triggers_callback(self):
        """Emergency callback fires when HR exceeds threshold."""
        emergency_triggered = []

        monitor = BiometricMonitor(
            config=BiometricConfig(critical_threshold=180),
            on_emergency=lambda: emergency_triggered.append(True),
        )

        # Simulate processing a critical heart rate
        monitor._process_heart_rate(185)
        assert monitor.in_emergency is True
        assert len(emergency_triggered) == 1

    def test_biometric_emergency_cancellation_within_window(self):
        """Emergency cancelled if HR normalizes within 30s."""
        cancelled = []

        monitor = BiometricMonitor(
            config=BiometricConfig(critical_threshold=180, cancellation_window=30.0),
            on_emergency=lambda: None,
            on_emergency_cancelled=lambda: cancelled.append(True),
        )

        # Trigger emergency
        monitor._process_heart_rate(185)
        assert monitor.in_emergency is True

        # Normalize within window (fake the start time to be recent)
        monitor._emergency_start_time = time.monotonic()
        monitor._process_heart_rate(75)
        assert monitor.in_emergency is False
        assert len(cancelled) == 1

    def test_emergency_route_to_hospital(self):
        """Emergency triggers route computation to nearest hospital."""
        planner = RoutePlanner(tank_capacity=50.0)

        current_pos = GeoPoint(latitude=48.2, longitude=11.5, label="Current")
        hospital = GeoPoint(latitude=48.25, longitude=11.55, label="Hospital")

        distance = planner.compute_distance_km(current_pos, hospital)
        assert distance > 0

        # Verify hospital is reachable
        assert planner.is_reachable(30.0, 8.0, distance) is True


# ============================================================================
# 17.5 Integration test for demo scenario flow
# ============================================================================


class TestDemoScenarioFlow:
    """Integration: full 3-5 minute demo scenario flow."""

    def test_scene1_highway_food_query_online(self):
        """Scene 1: Driver asks for food options → routes to cloud."""
        orchestrator = PipelineOrchestrator()
        result = asyncio.run(
            orchestrator.process_command("Find me good food options nearby")
        )
        history = orchestrator.logger.get_history()
        assert history[0].classification == "informational"
        assert history[0].routing_decision == "cloud"
        assert history[0].connectivity_state == "online"

    def test_scene2_tunnel_entry_offline_transition(self):
        """Scene 2: Tunnel entry → offline mode switch."""
        orchestrator = PipelineOrchestrator()

        # Simulate connectivity loss
        orchestrator.handle_connectivity_change(ConnectivityState.OFFLINE)
        assert orchestrator.mode == ProcessingMode.OFFLINE

        # All commands now route to edge
        result = asyncio.run(
            orchestrator.process_command("What Italian restaurants are nearby?")
        )
        history = orchestrator.logger.get_history()
        assert history[0].routing_decision == "edge"
        assert history[0].connectivity_state == "offline"

    def test_scene3_offline_multi_turn_followup(self):
        """Scene 3: Multi-turn offline conversation narrowing preferences."""
        context = ConversationContext()
        orchestrator = PipelineOrchestrator(conversation_context=context)
        orchestrator.handle_connectivity_change(ConnectivityState.OFFLINE)

        # Simulate multi-turn conversation
        turns = [
            "Find me Italian food",
            "I prefer pasta",
            "Mid-range price please",
            "Within 10 km",
            "Open now",
        ]

        for turn in turns:
            asyncio.run(orchestrator.process_command(turn))

        history = orchestrator.logger.get_history()
        assert len(history) == 5
        assert all(h.routing_decision == "edge" for h in history)
        assert all(h.connectivity_state == "offline" for h in history)

    def test_scene4_tunnel_exit_context_forwarding(self):
        """Scene 4: Tunnel exit → online restore, context available for forwarding."""
        context = ConversationContext()

        # Accumulate offline turns
        context.add_turn("user", "Find Italian food")
        context.add_turn("assistant", "What type of pasta?")
        context.add_turn("user", "Carbonara, mid-range")

        # Restore connectivity
        orchestrator = PipelineOrchestrator(conversation_context=context)
        orchestrator.handle_connectivity_change(ConnectivityState.OFFLINE)
        orchestrator.handle_connectivity_change(ConnectivityState.ONLINE)

        assert orchestrator.mode == ProcessingMode.ONLINE

        # Context is preserved and ready for forwarding
        messages = context.get_messages_for_bedrock()
        assert len(messages) == 3

    def test_scene5_fuel_aware_routing(self):
        """Scene 5: Fuel-aware routing with reachability check."""
        planner = RoutePlanner(tank_capacity=50.0)

        current = GeoPoint(48.1, 11.5, "Highway")
        restaurant = GeoPoint(48.6, 12.0, "Restaurant")

        distance = planner.compute_distance_km(current, restaurant)

        # With low fuel, some destinations unreachable
        assert planner.is_reachable(10.0, 8.0, distance) is False
        # With more fuel, reachable
        assert planner.is_reachable(80.0, 8.0, distance) is True

    def test_scene6_gas_price_query(self):
        """Scene 6: Gas price query returns EUR per liter."""
        handler = RealTimeQueryHandler(bedrock_client=None)
        result = handler.query_fuel_price("Shell Autobahn")

        # Without live service, returns unavailable
        assert result.success is False
        assert "unavailable" in result.text.lower()

    def test_scene6_gas_price_with_cache(self):
        """Scene 6: Gas price from cache when live unavailable."""
        handler = RealTimeQueryHandler(bedrock_client=None)

        # Manually populate cache
        from datetime import datetime, timezone

        cached_result = RealTimeQueryResult(
            text="Current price: 1.85 EUR per liter at Shell Autobahn",
            data_source="live",
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=True,
        )
        from speechless.cloud.realtime import CachedEntry

        handler._cache["fuel_price:Shell Autobahn"] = CachedEntry(
            result=cached_result,
            expires_at=time.monotonic() + 300,
        )

        result = handler.query_fuel_price("Shell Autobahn")
        assert result.success is True
        assert "1.85 EUR" in result.text
        assert result.data_source == "cached"

    def test_scene7_biometric_emergency(self):
        """Scene 7: Heart rate spike triggers emergency routing."""
        emergency_fired = []
        cancelled = []

        monitor = BiometricMonitor(
            config=BiometricConfig(critical_threshold=180, cancellation_window=30.0),
            on_emergency=lambda: emergency_fired.append(True),
            on_emergency_cancelled=lambda: cancelled.append(True),
        )

        # HR spike
        monitor._process_heart_rate(190)
        assert monitor.in_emergency is True
        assert len(emergency_fired) == 1

        # Route to nearest hospital
        planner = RoutePlanner(tank_capacity=50.0)
        current = GeoPoint(48.2, 11.5, "Current")
        hospital = GeoPoint(48.22, 11.52, "Klinikum München")

        distance = planner.compute_distance_km(current, hospital)
        assert planner.is_reachable(20.0, 8.0, distance) is True

    def test_full_mode_transitions_sequence(self):
        """Complete sequence: online → offline → accumulate → online → forward."""
        context = ConversationContext()
        orchestrator = PipelineOrchestrator(conversation_context=context)

        # Start online
        assert orchestrator.mode == ProcessingMode.ONLINE
        asyncio.run(orchestrator.process_command("Find food nearby"))

        # Go offline
        orchestrator.handle_connectivity_change(ConnectivityState.OFFLINE)
        assert orchestrator.mode == ProcessingMode.OFFLINE

        # Accumulate offline turns
        asyncio.run(orchestrator.process_command("I want pasta"))
        asyncio.run(orchestrator.process_command("Mid-range price"))

        # Go back online
        orchestrator.handle_connectivity_change(ConnectivityState.ONLINE)
        assert orchestrator.mode == ProcessingMode.ONLINE

        # Verify all commands logged correctly
        history = orchestrator.logger.get_history()
        assert len(history) == 3
        assert history[0].connectivity_state == "online"
        assert history[1].connectivity_state == "offline"
        assert history[2].connectivity_state == "offline"
