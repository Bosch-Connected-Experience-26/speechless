# Hybrid Voice Assistant — System Architecture

## High-Level Architecture

```mermaid
graph TB
    subgraph User["👤 Driver"]
        MIC[🎤 Microphone Input]
    end

    subgraph VoiceAssistant["Hybrid Voice Assistant System"]
        
        subgraph IntentParsing["Intent Parser"]
            STT[Speech-to-Text]
            NLU[Pattern Matching + NLU]
            SAFETY[Safety Criticality<br/>Classifier]
        end

        subgraph Router["Hybrid Router"]
            DECISION{Routing<br/>Decision}
            NETMON[Network Monitor]
        end

        subgraph Edge["Edge Processing (Jetson Nano)"]
            EDGE_EXEC[Edge Command<br/>Executor]
            LOCAL_MODEL[Local Intent<br/>Recognition]
        end

        subgraph Cloud["Cloud Processing"]
            CLOUD_EXEC[Cloud Command<br/>Executor]
            LLM[LLM / GenAI<br/>Services]
            MAPS[Maps & Places<br/>APIs]
        end

        subgraph VehicleLayer["Vehicle Control Layer"]
            VSI[Vehicle Command<br/>Interface]
            KUKSA[KUKSA VSS<br/>Protocol]
            SIM[Simulated<br/>Vehicle]
        end
    end

    subgraph Vehicle["🚗 Vehicle Systems"]
        STEER[Steering]
        BRAKE[Brakes]
        LIGHTS[Lights]
        HVAC[Climate / HVAC]
        MEDIA[Media System]
    end

    subgraph Dashboard["📊 Visual Dashboard (Flask)"]
        CARVIS[Car Visualization]
        SPEEDO[Speedometer]
        SIGNAL[Signal Strength]
        LOGS[Event Log]
    end

    MIC --> STT
    STT --> NLU
    NLU --> SAFETY
    SAFETY --> DECISION
    NETMON --> DECISION

    DECISION -->|"CRITICAL: < 50ms"| EDGE_EXEC
    DECISION -->|"Complex Reasoning"| CLOUD_EXEC
    DECISION -->|"Both Viable"| EDGE_EXEC
    DECISION -->|"Both Viable"| CLOUD_EXEC

    CLOUD_EXEC --> LLM
    CLOUD_EXEC --> MAPS

    EDGE_EXEC --> VSI
    CLOUD_EXEC --> VSI
    VSI --> KUKSA
    VSI --> SIM

    KUKSA --> STEER
    KUKSA --> BRAKE
    KUKSA --> LIGHTS
    KUKSA --> HVAC
    KUKSA --> MEDIA

    VSI --> Dashboard
```

## Routing Decision Flow

```mermaid
flowchart TD
    START([Voice Command<br/>Received]) --> PARSE[Parse Intent &<br/>Parameters]
    PARSE --> CLASSIFY{Safety<br/>Criticality?}
    
    CLASSIFY -->|CRITICAL<br/>steering, braking| EDGE_ONLY[Execute on Edge<br/>< 50ms guaranteed]
    CLASSIFY -->|HIGH<br/>lights, signals| CHECK_NET{Network<br/>Reliable?}
    CLASSIFY -->|MEDIUM<br/>climate, volume| CHECK_NET
    CLASSIFY -->|LOW<br/>navigation, music| CLOUD_PREF[Prefer Cloud]
    
    CHECK_NET -->|Yes| PARALLEL[Parallel Execution<br/>Fastest-Wins]
    CHECK_NET -->|No| EDGE_FALLBACK[Edge Fallback]
    
    CLOUD_PREF --> CHECK_CONN{Connected?}
    CHECK_CONN -->|Yes| CLOUD_EXEC[Cloud Execution]
    CHECK_CONN -->|No| EDGE_FALLBACK
    
    EDGE_ONLY --> RESULT([Execution Result])
    PARALLEL --> RESULT
    EDGE_FALLBACK --> RESULT
    CLOUD_EXEC --> RESULT

    style EDGE_ONLY fill:#ff6b6b,color:#fff
    style CLOUD_EXEC fill:#4dabf7,color:#fff
    style PARALLEL fill:#51cf66,color:#fff
    style EDGE_FALLBACK fill:#ffd43b,color:#000
```

## Component Breakdown

```mermaid
graph LR
    subgraph Core["src/alpacai/core/voice_assistant/"]
        HR[hybrid_router.py<br/>━━━━━━━━━━━━<br/>• NetworkMonitor<br/>• EdgeCommandExecutor<br/>• CloudCommandExecutor<br/>• HybridVoiceRouter]
        IP[intent_parser.py<br/>━━━━━━━━━━━━<br/>• VoiceIntentParser<br/>• IntentPattern<br/>• Regex matching<br/>• Parameter extraction]
        VC[vehicle_control.py<br/>━━━━━━━━━━━━<br/>• VehicleCommandInterface<br/>• SimulatedVehicleControl<br/>• KuksaVehicleControl]
    end

    subgraph Entry["Entry Points"]
        DASH[run_visual_dashboard.py<br/>━━━━━━━━━━━━<br/>Flask web dashboard<br/>Real-time visualization]
        CLI[run_hybrid_voice_<br/>assistant_demo.py<br/>━━━━━━━━━━━━<br/>CLI demo with<br/>3 network scenarios]
    end

    IP --> HR
    HR --> VC
    Entry --> Core
```

## Latency Targets

| Command Type | Target Latency | Execution Location | Example |
|---|---|---|---|
| Safety-Critical | **< 50ms** | Edge Only | Emergency brake, steering |
| High Priority | **< 100ms** | Edge Primary | Hazard lights, turn signals |
| Standard | **< 500ms** | Parallel (fastest-wins) | Climate, volume |
| Complex | **< 2000ms** | Cloud Primary | Navigation, restaurant search |

## Network Degradation Strategy

```mermaid
stateDiagram-v2
    [*] --> Normal: Connected & Low Latency
    Normal --> Degraded: Latency > 500ms
    Normal --> Offline: Connection Lost
    Degraded --> Normal: Latency Recovers
    Degraded --> Offline: Connection Lost
    Offline --> Degraded: Partial Recovery
    Offline --> Normal: Full Recovery

    state Normal {
        [*] --> CloudAvailable
        CloudAvailable: Cloud + Edge parallel
        CloudAvailable: Complex → Cloud
        CloudAvailable: Safety → Edge
    }

    state Degraded {
        [*] --> EdgePrimary
        EdgePrimary: All commands → Edge
        EdgePrimary: Cloud only if required
        EdgePrimary: Increased timeouts
    }

    state Offline {
        [*] --> EdgeOnly
        EdgeOnly: All commands → Edge
        EdgeOnly: Cloud queue for later
        EdgeOnly: Reduced functionality
    }
```

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Voice Input | Google Cloud Speech / Local ASR | Speech-to-text |
| Intent Parsing | Regex patterns + LLM fallback | Command understanding |
| Edge Runtime | Jetson Nano (Python 3.10+) | Local command execution |
| Cloud AI | Vertex AI / Gemini | Complex reasoning |
| Vehicle Protocol | Eclipse KUKSA (VSS) | Vehicle signal access |
| Dashboard | Flask + SVG + JavaScript | Real-time visualization |
| Container | Docker Compose | Deployment |
