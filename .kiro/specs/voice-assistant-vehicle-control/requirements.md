# Requirements Document

## Introduction

Speechless is a hybrid AI-powered in-vehicle voice assistant built by team LosRudos for the Voice Assistant for Vehicle Control hackathon challenge. The system intelligently routes voice commands between edge and cloud processing to enable fast, reliable, real-time vehicle control. Edge processing handles all vehicle control commands (HVAC, windows, lights, locks) for low-latency safety-critical operations, while cloud processing handles informational queries such as navigation, search, and conversational AI.

The system uses a local Whisper model for speech-to-text on the edge device with cloud fallback, and integrates with the Kuksa Vehicle API (gRPC) for vehicle actuation and telemetry reading (GPS, fuel level, biometrics). The edge inference layer supports dual deployment targets: LM Studio (OpenAI-compatible API on localhost) for development and NVIDIA Jetson (TensorRT/CUDA acceleration) for production. Cloud LLM processing uses AWS Bedrock (converse API) authenticated via the "losrudos" AWS CLI profile.

The system is connectivity-aware, seamlessly transitioning between cloud and edge-only modes based on network state. When offline, the local edge model supports multi-turn conversational follow-ups to refine user intent. When connectivity is restored, accumulated context is sent to AWS Bedrock for enriched cloud responses. Vehicle telemetry integration provides location, fuel, and biometric awareness for route planning, fuel-constrained destination suggestions, and emergency response. The implementation language is Python, and the demo scope covers a 3-5 minute scripted scenario demonstrating online/offline transitions, fuel-aware routing, and biometric emergency response.

## Glossary

- **Edge_Processor**: The local on-device computing unit responsible for speech-to-text transcription, vehicle control command execution, and offline conversational follow-ups with minimal latency
- **Cloud_Processor**: The remote cloud-based system responsible for handling informational queries, real-time data lookups, and enriched conversational AI responses via AWS Bedrock
- **Command_Router**: The classification component that analyzes transcribed text and determines whether a command should be processed locally on edge or forwarded to the cloud
- **Speech_Engine**: The speech-to-text component that converts spoken audio input into text using a local Whisper model, with cloud fallback capability
- **Vehicle_Controller**: The component that translates parsed vehicle control intents into Kuksa Vehicle API gRPC calls to actuate vehicle systems
- **Kuksa_API**: The Eclipse Kuksa Vehicle Abstraction Layer accessed via gRPC, used to read and write vehicle signal values (HVAC, windows, lights, locks, GPS, fuel, biometrics)
- **Voice_Assistant**: The top-level Speechless system encompassing all components end-to-end
- **Wake_Word**: An optional activation phrase that triggers the voice assistant to begin listening for commands
- **Edge_LLM**: The local large language model running on edge hardware, compatible with LM Studio (OpenAI-compatible API on localhost) for development and NVIDIA Jetson (TensorRT/CUDA) for production deployment
- **Bedrock_Client**: The AWS Bedrock client component that sends queries to cloud LLMs using the converse API, authenticated via the "losrudos" AWS CLI profile
- **Connectivity_Monitor**: The component that detects network connectivity state (online/offline) and orchestrates transitions between cloud and edge-only processing modes
- **Conversation_Context**: The accumulated multi-turn conversation history maintained by the Edge_LLM during offline interactions, queued for cloud enrichment upon connectivity restoration
- **Telemetry_Reader**: The component that reads vehicle telemetry data (GPS position, fuel level, fuel consumption rate, biometrics) from the Kuksa_API via VSS paths
- **Route_Planner**: The component that computes reachable destinations based on remaining fuel, suggests optimal routes with minimal deviations, and applies constraints (refueling, food stops)
- **Biometric_Monitor**: The component that reads driver biometric signals (heart rate) from vehicle sensors via Kuksa VSS and triggers emergency routing when critical thresholds are exceeded
- **VSS**: Vehicle Signal Specification — the standardized path format for vehicle data signals used by Kuksa

## Requirements

### Requirement 1: Speech-to-Text Capture

**User Story:** As a driver, I want to speak commands naturally so that I can control my vehicle without physical interaction.

#### Acceptance Criteria

1. WHEN the driver speaks a command, THE Speech_Engine SHALL capture audio input from the vehicle microphone and produce a text transcription using the local Whisper model.
2. WHEN the local Whisper model produces a transcription with confidence below a defined threshold, THE Speech_Engine SHALL forward the audio to a cloud-based speech recognition service for re-transcription.
3. IF the cloud speech recognition service is unavailable, THEN THE Speech_Engine SHALL use the local transcription result regardless of confidence level.
4. WHEN transcription completes, THE Speech_Engine SHALL pass the resulting text to the Command_Router within 500 milliseconds of audio capture completion. IF transcription completes after the 500ms deadline, THEN THE Speech_Engine SHALL still pass the text to the Command_Router rather than abandoning it.

### Requirement 2: Command Classification and Routing

**User Story:** As a driver, I want my voice commands to be handled by the right system so that vehicle controls respond instantly and informational requests get rich answers.

#### Acceptance Criteria

1. WHEN the Command_Router receives transcribed text, THE Command_Router SHALL classify the command as either a vehicle control command or an informational query.
2. WHEN the Command_Router classifies a command as a vehicle control command, THE Command_Router SHALL route the command to the Edge_Processor for local execution. THE Command_Router MAY route based on preliminary category identification before full classification completes.
3. WHEN the Command_Router classifies a command as an informational query, THE Command_Router SHALL route the command to the Cloud_Processor for remote processing.
4. THE Command_Router SHALL complete classification and routing within 100 milliseconds of receiving transcribed text.
5. IF the Command_Router cannot determine the command category with sufficient confidence, THEN THE Command_Router SHALL default to routing the command to the Cloud_Processor.

### Requirement 3: Edge Vehicle Control Execution

**User Story:** As a driver, I want vehicle control commands (HVAC, windows, lights, locks) to execute immediately so that I experience responsive and safe vehicle interaction.

#### Acceptance Criteria

1. WHEN the Edge_Processor receives a vehicle control command, THE Vehicle_Controller SHALL parse the intent and target vehicle system from the command text.
2. WHEN the Vehicle_Controller identifies a valid vehicle control intent, THE Vehicle_Controller SHALL send the corresponding gRPC request to the Kuksa_API to actuate the target vehicle signal.
3. THE Vehicle_Controller SHALL support a minimum of 3 vehicle control commands including HVAC temperature adjustment, window open/close, and door lock/unlock.
4. WHEN the Kuksa_API confirms successful signal actuation, THE Voice_Assistant SHALL provide audible or visual confirmation to the driver in strictly less than 1 second from the original voice command.
5. IF the Kuksa_API returns an error or is unreachable, THEN THE Vehicle_Controller SHALL inform the driver of the failure with a descriptive error message.

### Requirement 4: Cloud Informational Query Processing

**User Story:** As a driver, I want to ask informational questions (navigation, general knowledge) and receive intelligent responses so that I stay informed without distraction.

#### Acceptance Criteria

1. WHEN the Cloud_Processor receives an informational query, THE Cloud_Processor SHALL forward the query to a cloud-based large language model or search service for processing.
2. WHEN the cloud service returns a response, THE Cloud_Processor SHALL deliver the response back to the Voice_Assistant for presentation to the driver.
3. IF the cloud service is unavailable or does not respond, THEN THE Cloud_Processor SHALL wait the full 5-second timeout period before informing the driver that the informational request cannot be completed at this time.
4. WHEN the Cloud_Processor receives a response, THE Voice_Assistant SHALL present the response to the driver via text-to-speech audio output.

### Requirement 5: System Integration and End-to-End Pipeline

**User Story:** As a driver, I want a seamless voice interaction experience from speaking a command to receiving feedback so that the system feels unified and reliable.

#### Acceptance Criteria

1. THE Voice_Assistant SHALL provide an end-to-end pipeline from audio capture through transcription, classification, execution, and response delivery.
2. WHEN the driver initiates a vehicle control command, THE Voice_Assistant SHALL complete the full pipeline from speech input to vehicle actuation confirmation within 2 seconds under normal operating conditions.
3. WHEN the driver initiates an informational query, THE Voice_Assistant SHALL begin delivering a response within 5 seconds under normal network conditions.
4. THE Voice_Assistant SHALL log each processed command with a timestamp, classification result, routing decision, and execution outcome for debugging and demo purposes.
5. IF any component in the pipeline encounters an unrecoverable error, THEN THE Voice_Assistant SHALL gracefully inform the driver and remain ready to accept the next command without requiring a restart.

### Requirement 6: Kuksa Vehicle API Integration

**User Story:** As a developer, I want the system to integrate with the Kuksa Vehicle API over gRPC so that vehicle signal manipulation uses a standardized automotive interface.

#### Acceptance Criteria

1. THE Vehicle_Controller SHALL maintain an active connected state to the Kuksa Vehicle API using gRPC protocol.
2. WHEN the Vehicle_Controller sends a vehicle signal write request, THE Vehicle_Controller SHALL use the standard Kuksa databroker gRPC interface with properly formatted VSS (Vehicle Signal Specification) paths.
3. THE Vehicle_Controller SHALL support reading current vehicle signal values from the Kuksa_API to confirm state changes after actuation.
4. IF the gRPC connection to the Kuksa_API is lost, THEN THE Vehicle_Controller SHALL attempt reconnection with exponential backoff up to 3 retries before reporting a connection failure.

### Requirement 7: Edge LLM Compatibility (LM Studio and NVIDIA Jetson)

**User Story:** As a developer, I want the edge inference layer to run on both my development machine (via LM Studio) and the production NVIDIA Jetson hardware so that I can develop and test locally with identical API interfaces.

#### Acceptance Criteria

1. THE Edge_LLM SHALL expose an OpenAI-compatible API interface for all local model interactions, enabling compatibility with LM Studio on localhost during development.
2. THE Edge_LLM SHALL support deployment on NVIDIA Jetson hardware using TensorRT and CUDA acceleration for production inference.
3. WHEN the Edge_LLM receives a prompt, THE Edge_LLM SHALL process the request using the same API contract (OpenAI chat completions format) regardless of whether the backend is LM Studio or Jetson TensorRT.
4. THE Voice_Assistant SHALL use a configuration parameter to select the edge inference target (LM Studio endpoint or Jetson endpoint) without requiring code changes.
5. WHEN the Edge_LLM is initialized, THE Edge_LLM SHALL validate connectivity to the configured endpoint and report readiness status within 3 seconds.

### Requirement 8: AWS Bedrock Cloud LLM Integration

**User Story:** As a developer, I want the system to use AWS Bedrock as the cloud LLM provider so that we leverage managed cloud AI services with team authentication.

#### Acceptance Criteria

1. THE Bedrock_Client SHALL use the AWS CLI profile "losrudos" for all authentication and configuration when connecting to AWS Bedrock services.
2. WHEN the Cloud_Processor receives an informational query, THE Bedrock_Client SHALL send the query to AWS Bedrock using the converse API.
3. WHEN AWS Bedrock returns a response via the converse API, THE Bedrock_Client SHALL extract the text content and deliver the response to the Voice_Assistant for presentation.
4. IF the AWS Bedrock service is unavailable or the "losrudos" profile credentials are expired, THEN THE Bedrock_Client SHALL return an error indicating the authentication or connectivity failure within 5 seconds.
5. THE Bedrock_Client SHALL include conversation history in converse API requests to support multi-turn cloud interactions when online.

### Requirement 9: Connectivity-Aware Processing

**User Story:** As a driver, I want the system to seamlessly handle network connectivity changes so that I always receive useful responses whether online or offline.

#### Acceptance Criteria

1. THE Connectivity_Monitor SHALL continuously detect the current network connectivity state (online or offline) by performing periodic connectivity checks.
2. WHEN the Connectivity_Monitor detects a transition from online to offline, THE Voice_Assistant SHALL switch to edge-only processing mode, routing all queries to the Edge_LLM.
3. WHEN the Connectivity_Monitor detects a transition from offline to online, THE Voice_Assistant SHALL resume cloud processing mode and send any accumulated Conversation_Context to the Bedrock_Client for enriched responses.
4. WHILE the system is in offline mode, THE Edge_LLM SHALL handle all informational queries locally using the configured local model.
5. WHEN connectivity is restored after an offline period, THE Bedrock_Client SHALL receive the accumulated offline conversation context and return an enriched response incorporating that context.
6. THE Connectivity_Monitor SHALL detect connectivity state changes within 5 seconds of the actual network transition.

### Requirement 10: Contextual Follow-up Conversations (Offline)

**User Story:** As a driver, I want to have multi-turn conversations with the assistant even when offline so that I can refine my requests without network dependency.

#### Acceptance Criteria

1. WHILE the system is in offline mode, THE Edge_LLM SHALL maintain a Conversation_Context that preserves the history of the current multi-turn interaction.
2. WHEN the driver asks a follow-up question while offline, THE Edge_LLM SHALL generate a response that considers all prior turns in the current Conversation_Context.
3. THE Edge_LLM SHALL support a minimum of 5 consecutive follow-up turns within a single offline conversation session.
4. WHEN the Edge_LLM generates a follow-up response, THE Edge_LLM SHALL produce a contextually relevant response within 3 seconds on the target edge hardware.
5. WHEN the system transitions from offline to online, THE Voice_Assistant SHALL preserve the accumulated Conversation_Context and make it available to the Bedrock_Client for context-enriched cloud processing.

### Requirement 11: Location and Fuel Awareness

**User Story:** As a driver, I want the assistant to know my current location, fuel level, and fuel consumption so that it can suggest reachable destinations and optimal routes.

#### Acceptance Criteria

1. THE Telemetry_Reader SHALL read current GPS position (latitude, longitude) from the Kuksa_API using the standard VSS path for vehicle location.
2. THE Telemetry_Reader SHALL read current fuel level (percentage or liters) from the Kuksa_API using the standard VSS path for fuel status.
3. THE Telemetry_Reader SHALL read fuel consumption rate (liters per 100km) from the Kuksa_API using the standard VSS path for fuel consumption.
4. WHEN the Route_Planner receives a destination query, THE Route_Planner SHALL compute whether the destination is reachable based on current fuel level, consumption rate, and distance to destination.
5. WHEN the Route_Planner determines that a destination is not reachable with current fuel, THE Route_Planner SHALL inform the driver that the destination is out of fuel range and suggest refueling options.

### Requirement 12: Route Planning with Constraints

**User Story:** As a driver, I want the assistant to suggest optimal routes that satisfy my constraints (refuel, eat at preferred choice) with minimal deviations from my path.

#### Acceptance Criteria

1. WHEN the driver requests a route with multiple constraints (refueling stop, food stop), THE Route_Planner SHALL compute a route that satisfies all constraints while minimizing total deviation from the direct path.
2. WHEN the Route_Planner identifies route options, THE Route_Planner SHALL rank options by total deviation distance and present the least-deviation option first.
3. IF a preferred food or fuel stop is outside the current fuel range, THEN THE Route_Planner SHALL alert the driver that the preferred option requires refueling first and suggest an alternative sequence.
4. WHEN the Route_Planner suggests a combined route (refuel and eat), THE Route_Planner SHALL present the estimated total deviation distance and additional travel time to the driver.
5. THE Route_Planner SHALL update route suggestions in real-time as the vehicle position and fuel level change during navigation.

### Requirement 13: Real-time Information Queries

**User Story:** As a driver, I want to query real-time data like fuel prices and restaurant availability so that I can make informed decisions while driving.

#### Acceptance Criteria

1. WHILE the system is in online mode, THE Cloud_Processor SHALL query real-time fuel price data from cloud services when the driver requests fuel price information.
2. WHILE the system is in online mode, THE Cloud_Processor SHALL query restaurant availability and operating hours from cloud services when the driver requests food options.
3. WHEN the Cloud_Processor retrieves real-time data, THE Voice_Assistant SHALL present the information to the driver with the data source and timestamp of the information.
4. IF real-time data services are unavailable, THEN THE Cloud_Processor SHALL inform the driver that live data is currently unavailable and provide cached information if available.
5. WHEN the driver asks about fuel prices at a specific station, THE Cloud_Processor SHALL return the current price per liter in the local currency (EUR).

### Requirement 14: Biometric Monitoring and Emergency Response

**User Story:** As a driver, I want the system to monitor my heart rate and automatically route to emergency services if a critical health event is detected so that I receive timely medical assistance.

#### Acceptance Criteria

1. THE Biometric_Monitor SHALL read driver heart rate data from vehicle sensors via the Kuksa_API using the standard VSS path for occupant biometrics.
2. THE Biometric_Monitor SHALL continuously monitor heart rate at a minimum sampling interval of 5 seconds.
3. WHEN the Biometric_Monitor detects a heart rate value exceeding the configured critical threshold (default: 180 BPM), THE Biometric_Monitor SHALL trigger an emergency response.
4. WHEN an emergency response is triggered, THE Route_Planner SHALL immediately compute the route to the nearest hospital or emergency services facility and present the route to the driver.
5. WHEN an emergency route is computed, THE Voice_Assistant SHALL audibly alert the driver with the emergency routing information and estimated time to the nearest facility.
6. IF the heart rate returns below the critical threshold within 30 seconds of the initial spike, THEN THE Biometric_Monitor SHALL cancel the emergency response and inform the driver that the alert was resolved.

### Requirement 15: Architectural Documentation

**User Story:** As a developer and evaluator, I want comprehensive architectural documentation so that the system design is clearly communicated and can be evaluated for quality.

#### Acceptance Criteria

1. THE Voice_Assistant project SHALL include a hyperdetailed architectural diagram in .drawio format that depicts all system components, their interactions, data flows, and deployment targets.
2. THE Voice_Assistant project SHALL include Mermaid sequence diagrams for all major system flows including: speech-to-command pipeline, online query processing, offline conversational follow-up, connectivity transition, fuel-aware route planning, and emergency biometric response.
3. THE Voice_Assistant project SHALL include use case diagrams that cover end-to-end testing scenarios for: vehicle control commands, informational queries, offline-to-online transitions, fuel-constrained routing, and emergency response.
4. THE architectural diagram SHALL clearly distinguish between edge components (running on Jetson/LM Studio) and cloud components (running on AWS Bedrock).
5. THE sequence diagrams SHALL include timing annotations showing expected latency for each step in the processing pipeline.

### Requirement 16: Demo Scenario Support (3-5 Minutes)

**User Story:** As a presenter, I want a scripted demo scenario that showcases all system capabilities in a compelling 3-5 minute narrative so that evaluators can see the full system in action.

#### Acceptance Criteria

1. THE Voice_Assistant SHALL support a demo scenario where the driver on a highway asks for food options, triggering a cloud query to AWS Bedrock for nearby restaurant information.
2. WHEN the demo simulates the driver entering a tunnel (network disconnection), THE Voice_Assistant SHALL transition to offline mode within 5 seconds and acknowledge the mode change.
3. WHILE in the tunnel (offline), THE Edge_LLM SHALL conduct multi-turn follow-up questions to narrow the driver's food preferences using the local model.
4. WHEN the demo simulates tunnel exit (connectivity restored), THE Voice_Assistant SHALL send accumulated conversation context to AWS Bedrock and return an enriched response combining offline preferences with cloud data.
5. WHEN food options are identified, THE Route_Planner SHALL compute reachable options based on remaining fuel and alert the driver that certain options are out of fuel range unless refueling occurs.
6. THE Route_Planner SHALL suggest gas stations along the route and present an optimal route (least deviations) that combines refueling and eating at the preferred location.
7. WHEN the driver asks about gasoline price, THE Cloud_Processor SHALL return the current price (e.g., "2.35 EUR per liter") from real-time data services.
8. WHEN the demo simulates a driver heart rate spike, THE Biometric_Monitor SHALL trigger emergency routing to the nearest hospital, demonstrating the biometric monitoring capability.
9. THE demo scenario SHALL complete within 3-5 minutes and exercise all major system capabilities: cloud queries, offline transitions, conversational follow-ups, fuel-aware routing, real-time data, and biometric emergency response.
