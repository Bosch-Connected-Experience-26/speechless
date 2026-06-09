# Use Case Diagrams

## Use Case 1: Vehicle Control Commands

```mermaid
graph LR
    Driver((Driver))
    
    subgraph "Vehicle Control Use Cases"
        UC1[Set HVAC Temperature]
        UC2[Open/Close Windows]
        UC3[Lock/Unlock Doors]
        UC4[Turn On/Off Lights]
    end
    
    subgraph "System Components"
        STT[Speech Engine]
        Router[Command Router]
        Parser[Intent Parser]
        VCtrl[Vehicle Controller]
        Kuksa[Kuksa Databroker]
        TTS[Response Engine]
    end
    
    Driver --> UC1
    Driver --> UC2
    Driver --> UC3
    Driver --> UC4
    
    UC1 --> STT
    UC2 --> STT
    UC3 --> STT
    UC4 --> STT
    
    STT --> Router
    Router --> Parser
    Parser --> VCtrl
    VCtrl --> Kuksa
    VCtrl --> TTS
    TTS --> Driver
```

## Use Case 2: Informational Queries

```mermaid
graph LR
    Driver((Driver))
    
    subgraph "Informational Query Use Cases"
        UC1[General Knowledge Query]
        UC2[Fuel Price Query]
        UC3[Restaurant Search]
        UC4[Navigation Query]
    end
    
    subgraph "System Components"
        STT[Speech Engine]
        Router[Command Router]
        Bedrock[AWS Bedrock]
        RealTime[Real-Time Handler]
        TTS[Response Engine]
    end
    
    Driver --> UC1
    Driver --> UC2
    Driver --> UC3
    Driver --> UC4
    
    UC1 --> STT
    UC2 --> STT
    UC3 --> STT
    UC4 --> STT
    
    STT --> Router
    Router --> Bedrock
    Router --> RealTime
    Bedrock --> TTS
    RealTime --> TTS
    TTS --> Driver
```

## Use Case 3: Offline-to-Online Transitions

```mermaid
graph TB
    Driver((Driver))
    
    subgraph "Connectivity Transition Use Cases"
        UC1[Continue Conversation Offline]
        UC2[Receive Enriched Response on Reconnection]
        UC3[Seamless Mode Switch]
    end
    
    subgraph "System"
        Monitor[Connectivity Monitor]
        EdgeLLM[Edge LLM]
        Context[Conversation Context]
        Bedrock[AWS Bedrock]
    end
    
    Driver --> UC1
    Driver --> UC2
    Driver --> UC3
    
    UC1 --> EdgeLLM
    UC1 --> Context
    UC2 --> Context
    UC2 --> Bedrock
    UC3 --> Monitor
    Monitor --> EdgeLLM
    Monitor --> Bedrock
```

## Use Case 4: Fuel-Constrained Routing

```mermaid
graph LR
    Driver((Driver))
    
    subgraph "Route Planning Use Cases"
        UC1[Check Destination Reachability]
        UC2[Find Refueling Stops]
        UC3[Multi-Constraint Route]
        UC4[Real-Time Route Updates]
    end
    
    subgraph "System"
        Telemetry[Telemetry Reader]
        Planner[Route Planner]
        TTS[Response Engine]
    end
    
    Driver --> UC1
    Driver --> UC2
    Driver --> UC3
    Driver --> UC4
    
    UC1 --> Telemetry
    UC2 --> Planner
    UC3 --> Planner
    UC4 --> Telemetry
    Telemetry --> Planner
    Planner --> TTS
    TTS --> Driver
```

## Use Case 5: Emergency Response

```mermaid
graph TB
    Driver((Driver))
    
    subgraph "Emergency Use Cases"
        UC1[Heart Rate Monitoring]
        UC2[Emergency Route to Hospital]
        UC3[Emergency Cancellation]
        UC4[Emergency Alert Announcement]
    end
    
    subgraph "System"
        Biometric[Biometric Monitor]
        Kuksa[Kuksa VSS]
        Planner[Route Planner]
        TTS[Response Engine]
    end
    
    Kuksa --> Biometric
    Biometric --> UC1
    UC1 --> UC2
    UC2 --> Planner
    UC2 --> UC4
    UC1 --> UC3
    UC3 --> TTS
    UC4 --> TTS
    TTS --> Driver
    Planner --> TTS
```
