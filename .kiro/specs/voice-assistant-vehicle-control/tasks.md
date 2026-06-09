# Implementation Plan: Voice Assistant Vehicle Control

## Overview

Implement the Speechless edge-first voice assistant with connectivity-aware processing, fuel-aware route planning, biometric emergency response, and comprehensive property-based testing. The system uses Python 3.11+, uv/hatchling for packaging, faster-whisper for local STT, openai client for edge LLM (dual targets: LM Studio dev + Jetson prod), boto3 for AWS Bedrock (profile "losrudos"), kuksa-client for vehicle gRPC, and hypothesis for property-based testing.

## Tasks

- [ ] 1. Project setup and core infrastructure
  - [x] 1.1 Create pyproject.toml with hatchling build, all dependencies, and dev extras
    - Configure uv package manager with hatchling build backend
    - Include all production deps: faster-whisper, sounddevice, numpy, pyttsx3, openai, boto3, grpcio, kuksa-client, httpx
    - Include dev deps: pytest, pytest-asyncio, hypothesis, ruff, mypy, moto
    - Configure pytest ini options and ruff settings
    - _Requirements: 5.1, 6.1, 7.1, 8.1_

  - [x] 1.2 Create Docker Compose configuration for Kuksa databroker
    - Define kuksa-databroker service with ghcr.io/eclipse-kuksa/kuksa-databroker:0.4.4
    - Expose port 55555 for gRPC, add healthcheck with grpc_health_probe
    - Mount vss-data volume for VSS signal definitions
    - _Requirements: 6.1, 6.2_

  - [x] 1.3 Create project directory structure and core modules
    - Create src/speechless/ package with all subpackages: speech, router, edge, cloud, connectivity, context, telemetry, routing, response, utils
    - Create __init__.py files for all packages
    - _Requirements: 5.1_

  - [-] 1.4 Implement data models and configuration
    - Create src/speechless/models.py with PipelineState, ProcessingMode, PipelineContext, AppConfig dataclasses
    - Create src/speechless/config.py loading config from environment variables with defaults for edge_target, bedrock_profile "losrudos", kuksa_host, ping_url, thresholds
    - _Requirements: 5.1, 7.4, 8.1_

  - [-] 1.5 Implement utility modules (retry with exponential backoff, structured logging)
    - Create src/speechless/utils/retry.py with RetryConfig, compute_backoff_delay, retry_sync functions
    - Create src/speechless/utils/logging.py with CommandLogEntry dataclass and CommandLogger class
    - Ensure log entries contain: timestamp, transcription, classification, routing_decision, execution_outcome, connectivity_state
    - _Requirements: 5.4, 6.4_

- [ ] 2. Speech Engine (local STT + cloud fallback)
  - [ ] 2.1 Implement audio capture module
    - Create src/speechless/speech/capture.py with AudioCapture class using sounddevice
    - Support configurable sample rate (16kHz default) and chunk duration
    - Return AudioSegment dataclass with samples, sample_rate, duration_seconds
    - _Requirements: 1.1_

  - [ ] 2.2 Implement local Whisper STT
    - Create src/speechless/speech/stt_local.py with LocalSTT class using faster-whisper
    - Implement transcribe() returning TranscriptionResult with text, confidence, source
    - Implement is_below_threshold() for confidence checking
    - Include _logprob_to_confidence conversion
    - _Requirements: 1.1, 1.2_

  - [ ] 2.3 Implement cloud STT fallback
    - Create src/speechless/speech/stt_cloud.py using openai Whisper API
    - Implement fallback logic: trigger when local confidence < threshold
    - If cloud unavailable, return local result regardless of confidence
    - Ensure transcription result passes to Command Router within 500ms target (soft deadline — always deliver)
    - _Requirements: 1.2, 1.3, 1.4_

  - [ ] 2.4 Write property test for confidence threshold cloud fallback
    - **Property 1: Confidence threshold triggers cloud fallback**
    - For any TranscriptionResult with confidence below threshold, verify Speech Engine forwards to cloud STT
    - **Validates: Requirements 1.2**

- [ ] 3. Command Router (keyword classification)
  - [ ] 3.1 Implement command classifier
    - Create src/speechless/router/classifier.py with CommandCategory enum, ClassificationResult, CommandClassifier
    - Implement keyword-based classification with VEHICLE_KEYWORDS set
    - Route vehicle_control → "edge", informational → "cloud"
    - Default to "cloud" when confidence is below ambiguity threshold
    - Ensure classification completes within 100ms
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 3.2 Write property test for classification completeness
    - **Property 2: Classification completeness**
    - For any non-empty text, verify classifier always returns valid ClassificationResult (never None)
    - **Validates: Requirements 2.1**

  - [ ] 3.3 Write property test for routing correctness
    - **Property 3: Routing correctness follows classification**
    - For any ClassificationResult, verify VEHICLE_CONTROL → "edge", INFORMATIONAL → "cloud", low confidence → "cloud"
    - **Validates: Requirements 2.2, 2.3, 2.5**

- [ ] 4. Edge Processor (intent parser + vehicle controller + Kuksa gRPC)
  - [ ] 4.1 Implement intent parser
    - Create src/speechless/edge/intent_parser.py with VehicleSystem, Action enums, VehicleIntent dataclass
    - Implement parse() method detecting HVAC, windows, doors, lights keywords
    - Extract parameters (temperature values, open/close/lock/unlock actions)
    - _Requirements: 3.1, 3.3_

  - [ ] 4.2 Implement vehicle controller with Kuksa gRPC integration
    - Create src/speechless/edge/vehicle_controller.py with VSSSignal, ActuationResult dataclasses
    - Implement VSS_MAPPING dictionary for intent → signal path translation
    - Implement intent_to_signal() mapping VehicleIntent to VSSSignal
    - Implement format_vss_path() validation (must start with "Vehicle.", ≥3 segments)
    - Implement generate_error_message() with system and action context
    - Implement gRPC connection with kuksa-client, exponential backoff reconnection (3 retries)
    - _Requirements: 3.2, 3.4, 3.5, 6.1, 6.2, 6.3, 6.4_

  - [ ] 4.3 Write property test for intent parsing
    - **Property 4: Intent parsing extracts system and action**
    - For any text with recognized vehicle keyword, verify non-None VehicleIntent with valid system and action
    - **Validates: Requirements 3.1**

  - [ ] 4.4 Write property test for intent-to-VSS signal mapping
    - **Property 5: Intent-to-VSS signal mapping correctness**
    - For any valid VehicleIntent, verify signal path starts with "Vehicle." and has ≥3 segments
    - **Validates: Requirements 3.2, 6.2**

  - [ ] 4.5 Write property test for error messages
    - **Property 6: Error messages are descriptive**
    - For any exception and VehicleIntent, verify error message contains system name and action name
    - **Validates: Requirements 3.5**

  - [ ] 4.6 Write property test for VSS path format validity
    - **Property 9: VSS path format validity**
    - For any VSS path from Vehicle Controller, verify "Vehicle." prefix, ≥3 segments, [A-Za-z0-9]+ pattern
    - **Validates: Requirements 6.2**

  - [ ] 4.7 Write property test for exponential backoff retry timing
    - **Property 10: Exponential backoff retry timing**
    - For any sequence of failures up to 3 retries, verify delay = base_delay × multiplier^N, max 3 attempts
    - **Validates: Requirements 6.4**

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Edge LLM Client (OpenAI-compatible, dual targets)
  - [ ] 6.1 Implement Edge LLM client
    - Create src/speechless/edge/edge_llm.py with EdgeLLMConfig, EdgeLLMResponse, EdgeLLMClient
    - Use openai client library with configurable base_url (LM Studio localhost:1234/v1 or Jetson endpoint)
    - Implement validate_connectivity() checking endpoint readiness within 3 seconds
    - Implement generate() using chat.completions.create with OpenAI format
    - Implement build_request_messages() assembling system + history + user message
    - Target switchable via config parameter without code changes
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 6.2 Write property test for Edge LLM API contract consistency
    - **Property 11: Edge LLM API contract consistency**
    - For any prompt and target config (lmstudio/jetson), verify identical request structure produced
    - **Validates: Requirements 7.3**

- [ ] 7. Cloud Processor (AWS Bedrock converse API)
  - [ ] 7.1 Implement Bedrock client
    - Create src/speechless/cloud/bedrock_client.py with BedrockResponse, ConversationMessage, BedrockClient
    - Use boto3.Session(profile_name="losrudos") for authentication
    - Implement converse() method using Bedrock converse API with message history
    - Implement inject_context() for offline context forwarding
    - Implement _build_messages() formatting history for Bedrock API
    - Handle timeout (5s) and credential expiration errors
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ] 7.2 Write property test for Bedrock message formatting
    - **Property 12: Bedrock converse API message formatting with history**
    - For any N messages + new user message, verify all N+1 in chronological order with role/content
    - **Validates: Requirements 8.2, 8.5**

  - [ ] 7.3 Write property test for Bedrock response extraction
    - **Property 13: Bedrock response extraction**
    - For any valid Bedrock response structure, verify text extracted without modification
    - **Validates: Requirements 8.3**

- [ ] 8. Connectivity Monitor (periodic ping, mode switching)
  - [ ] 8.1 Implement connectivity monitor
    - Create src/speechless/connectivity/monitor.py with ConnectivityState, ConnectivityConfig, ConnectivityMonitor
    - Use httpx for periodic ping to configurable URL (default: Google generate_204)
    - Implement async check_connectivity() and run() loop with configurable interval (3s)
    - Fire on_state_change callback on transitions (ONLINE↔OFFLINE)
    - Detect state changes within 5 seconds of actual transition
    - _Requirements: 9.1, 9.2, 9.3, 9.6_

  - [ ] 8.2 Write property test for offline mode routing
    - **Property 14: Offline mode routes all queries to Edge LLM**
    - For any query while OFFLINE, verify routing to Edge LLM regardless of classification
    - **Validates: Requirements 9.2, 9.4**

- [ ] 9. Conversation Context Manager (offline multi-turn history)
  - [ ] 9.1 Implement conversation context manager
    - Create src/speechless/context/conversation.py with ConversationTurn, ConversationContext
    - Implement add_turn() with max_turns trimming (default 20)
    - Implement get_messages_for_llm() (OpenAI format) and get_messages_for_bedrock() (ConversationMessage format)
    - Support minimum 5 consecutive follow-up turns
    - Implement clear() and is_empty()
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 9.2 Write property test for context forwarding on reconnection
    - **Property 15: Context forwarding on connectivity restoration**
    - For any N-turn context, verify all N turns forwarded to Bedrock on offline→online transition
    - **Validates: Requirements 9.3, 9.5, 10.5**

  - [ ] 9.3 Write property test for offline conversation accumulation
    - **Property 16: Offline conversation context accumulation**
    - For K offline interactions, verify context contains K user+assistant turns and K+1th request includes all
    - **Validates: Requirements 10.1, 10.2**

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Telemetry Reader (GPS, fuel, consumption from Kuksa VSS)
  - [ ] 11.1 Implement telemetry reader
    - Create src/speechless/telemetry/reader.py with VehicleTelemetry dataclass, TelemetryReader class
    - Define VSS_PATHS mapping for latitude, longitude, fuel_level, fuel_consumption, heart_rate
    - Implement async read_gps(), read_fuel_level(), read_fuel_consumption(), read_heart_rate(), read_all()
    - Handle read failures gracefully (return None)
    - _Requirements: 11.1, 11.2, 11.3, 14.1_

- [ ] 12. Route Planner (fuel-aware reachability, multi-constraint routing)
  - [ ] 12.1 Implement route planner
    - Create src/speechless/routing/planner.py with GeoPoint, RouteConstraint, RouteOption, RoutePlanner
    - Implement compute_range_km() from fuel level and consumption rate
    - Implement is_reachable() checking destination within fuel range
    - Implement compute_distance_km() using Haversine formula
    - Implement rank_routes() sorting by total_deviation_km ascending
    - Implement compute_route_with_constraints() satisfying fuel/food/hospital stops with minimal deviation
    - Include warnings when stops are outside fuel range
    - Support real-time route updates as position/fuel change
    - _Requirements: 11.4, 11.5, 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ] 12.2 Write property test for fuel reachability computation
    - **Property 17: Fuel reachability computation correctness**
    - For any fuel_level, consumption_rate > 0, distance ≥ 0, verify reachable iff (fuel/100 × tank / rate) × 100 ≥ distance
    - **Validates: Requirements 11.4, 11.5**

  - [ ] 12.3 Write property test for route ranking
    - **Property 18: Route options ranked by deviation**
    - For any list of RouteOptions, verify sorted ascending by total_deviation_km
    - **Validates: Requirements 12.2**

  - [ ] 12.4 Write property test for route constraint satisfaction
    - **Property 19: Route constraint satisfaction**
    - For any route option, verify constraints_satisfied map to waypoints and out-of-range stops have warnings
    - **Validates: Requirements 12.1, 12.3**

  - [ ] 12.5 Write property test for combined route metadata
    - **Property 20: Combined route includes deviation and time metadata**
    - For any multi-constraint route option, verify total_deviation_km ≥ 0 and additional_time_minutes ≥ 0
    - **Validates: Requirements 12.4**

- [ ] 13. Biometric Monitor (heart rate, emergency threshold, auto-routing)
  - [ ] 13.1 Implement biometric monitor
    - Create src/speechless/telemetry/biometric.py with BiometricConfig, BiometricMonitor
    - Implement is_critical() checking HR ≥ threshold (default 180 BPM)
    - Implement async run() loop sampling every 5 seconds
    - Fire on_emergency callback when threshold exceeded
    - Implement cancellation: if HR normalizes within 30s, cancel emergency and fire on_emergency_cancelled
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [ ] 13.2 Write property test for biometric emergency threshold
    - **Property 21: Biometric emergency threshold detection**
    - For any HR value, verify emergency triggered iff HR ≥ critical_threshold
    - **Validates: Requirements 14.3**

  - [ ] 13.3 Write property test for emergency cancellation
    - **Property 22: Emergency cancellation within time window**
    - For any emergency state, verify cancellation if HR drops below threshold within 30s window
    - **Validates: Requirements 14.6**

- [ ] 14. Response Engine (TTS, confirmations, error announcements)
  - [ ] 14.1 Implement response engine with TTS
    - Create src/speechless/response/tts.py with ResponseEngine class using pyttsx3
    - Implement speak() for text-to-speech output
    - Implement confirm_actuation() for vehicle control success messages
    - Implement announce_error() for failure descriptions
    - Implement emergency_alert() for biometric emergency routing announcements
    - _Requirements: 3.4, 3.5, 4.4, 5.5, 14.5_

- [ ] 15. Pipeline Orchestrator (wires all components, mode-aware routing, state machine)
  - [ ] 15.1 Implement pipeline orchestrator and main entry point
    - Create src/speechless/main.py wiring all components together
    - Implement PipelineState state machine: IDLE → LISTENING → TRANSCRIBING → CLASSIFYING → EXECUTING → RESPONDING
    - Implement mode-aware routing: ONLINE+VEHICLE_CONTROL→Edge, ONLINE+INFORMATIONAL→Cloud, OFFLINE+any→EdgeLLM
    - Integrate Connectivity Monitor callbacks for mode switching
    - Integrate Biometric Monitor callbacks for emergency routing
    - Forward accumulated context to Bedrock on offline→online transition
    - Log every command with CommandLogger (timestamp, classification, routing, outcome)
    - Handle unrecoverable errors gracefully: notify driver, reset to IDLE
    - Enforce timing targets: vehicle control <2s end-to-end, informational <5s response start
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 9.2, 9.3_

  - [ ] 15.2 Write property test for log entry completeness
    - **Property 7: Log entry completeness**
    - For any processed command, verify CommandLogEntry has ISO timestamp, transcription, valid classification/routing/outcome/connectivity values
    - **Validates: Requirements 5.4**

  - [ ] 15.3 Write property test for error recovery
    - **Property 8: Error recovery preserves ready state**
    - For any error at any pipeline stage, verify state returns to IDLE without restart
    - **Validates: Requirements 5.5**

- [ ] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Integration tests and end-to-end flows
  - [ ] 17.1 Write integration tests for speech-to-command pipeline
    - Test full pipeline: mocked audio → LocalSTT → CommandClassifier → Edge/Cloud routing
    - Test cloud fallback when local confidence is low
    - Test graceful handling when cloud STT unavailable
    - Use moto for AWS Bedrock mocking
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 5.1_

  - [ ] 17.2 Write integration tests for vehicle control flow
    - Test intent parsing → VSS signal mapping → mocked Kuksa gRPC actuation → confirmation
    - Test HVAC, window, door lock commands end-to-end
    - Test Kuksa connection failure with exponential backoff retry
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 6.1, 6.4_

  - [ ] 17.3 Write integration tests for connectivity transitions
    - Test online→offline mode switch routing all queries to Edge LLM
    - Test offline→online restoration with context forwarding to Bedrock
    - Test multi-turn offline conversation accumulation (5+ turns)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 10.1, 10.2, 10.3_

  - [ ] 17.4 Write integration tests for route planning and biometric flows
    - Test fuel reachability computation with telemetry reader mock
    - Test multi-constraint routing with deviation ranking
    - Test biometric emergency trigger → route to hospital
    - Test emergency cancellation within 30s window
    - _Requirements: 11.4, 12.1, 12.2, 14.3, 14.4, 14.5, 14.6_

  - [ ] 17.5 Write integration test for demo scenario flow
    - Script the 3-5 minute demo: highway food query → tunnel offline → multi-turn follow-up → tunnel exit → enriched response → fuel-aware routing → gas price query → biometric emergency
    - Verify all mode transitions, context forwarding, and emergency response
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8, 16.9_

- [ ] 18. Architectural documentation
  - [ ] 18.1 Create hyperdetailed .drawio architectural diagram
    - Create docs/architecture.drawio with layers: Edge, Cloud, Vehicle, Orchestration, Data Flow
    - Depict all components, interactions, data flows, deployment targets
    - Distinguish edge (blue), cloud (orange), vehicle (green) components
    - Show LM Studio vs Jetson targets, AWS Bedrock with losrudos profile, Kuksa gRPC
    - _Requirements: 15.1, 15.4_

  - [ ] 18.2 Create Mermaid sequence diagrams
    - Create docs/diagrams/ directory with sequence diagrams as .md files
    - Include: speech-to-command pipeline, online query processing, offline conversational follow-up, connectivity transition, fuel-aware route planning, emergency biometric response
    - Add timing annotations for each step latency
    - _Requirements: 15.2, 15.5_

  - [ ] 18.3 Create use case diagrams
    - Create use case diagrams covering: vehicle control commands, informational queries, offline-to-online transitions, fuel-constrained routing, emergency response
    - _Requirements: 15.3_

- [ ] 19. Demo scenario script
  - [ ] 19.1 Create scripted demo scenario (3-5 minutes)
    - Create docs/demo_script.md with step-by-step demo narrative
    - Scene 1: Highway food query (cloud, Bedrock)
    - Scene 2: Tunnel entry (offline transition, mode switch acknowledgment)
    - Scene 3: Offline follow-ups (multi-turn preference narrowing via Edge LLM)
    - Scene 4: Tunnel exit (online restoration, context forwarding, enriched response)
    - Scene 5: Fuel-aware routing (reachable options, refueling suggestion, deviation)
    - Scene 6: Gas price query (real-time cloud data, EUR)
    - Scene 7: Biometric emergency (HR spike, hospital routing, alert)
    - Include expected system outputs and timing for each scene
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8, 16.9_

- [ ] 20. Real-time information query support
  - [ ] 20.1 Implement real-time data query support in Cloud Processor
    - Extend cloud processor to handle fuel price queries (return EUR per liter)
    - Extend cloud processor to handle restaurant availability queries
    - Include data source and timestamp in responses
    - Return cached data when live services unavailable
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based test tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- All 22 correctness properties from the design are covered by property test sub-tasks
- Checkpoints at tasks 5, 10, 16, and 21 ensure incremental validation
- Property tests use pytest + hypothesis with minimum 100 examples per property
- Integration tests use moto for AWS Bedrock mocking and mocked Kuksa gRPC client
- Docker Compose must be running for any Kuksa-dependent integration tests
- AWS CLI profile "losrudos" must be configured for Bedrock integration tests (mocked via moto in CI)
- Edge LLM tests mock the OpenAI client to avoid requiring a running LM Studio instance

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4", "1.5"] },
    { "id": 2, "tasks": ["2.1", "2.2", "3.1", "4.1"] },
    { "id": 3, "tasks": ["2.3", "2.4", "3.2", "3.3", "4.2"] },
    { "id": 4, "tasks": ["4.3", "4.4", "4.5", "4.6", "4.7", "6.1"] },
    { "id": 5, "tasks": ["6.2", "7.1", "8.1", "9.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "8.2", "9.2", "9.3"] },
    { "id": 7, "tasks": ["11.1", "13.1", "14.1"] },
    { "id": 8, "tasks": ["12.1", "13.2", "13.3"] },
    { "id": 9, "tasks": ["12.2", "12.3", "12.4", "12.5", "15.1"] },
    { "id": 10, "tasks": ["15.2", "15.3", "20.1"] },
    { "id": 11, "tasks": ["17.1", "17.2", "17.3", "17.4"] },
    { "id": 12, "tasks": ["17.5", "18.1", "18.2", "18.3"] },
    { "id": 13, "tasks": ["19.1"] }
  ]
}
```
