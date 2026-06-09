#!/usr/bin/env python3
"""
Hybrid Voice Assistant Demo
============================

Demonstrates intelligent edge-cloud routing for vehicle voice commands.

Features:
- Pattern-based intent recognition (fast, local)
- Latency-aware routing decisions
- Graceful fallback between edge and cloud
- Network condition awareness
- Real-time performance metrics
"""

import asyncio
import logging
import os
import sys
import time
from typing import List
from dataclasses import asdict
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'alpacai', 'core'))

from voice_assistant.hybrid_router import (
    HybridVoiceRouter, 
    EdgeCommandExecutor,
    CloudCommandExecutor,
    NetworkMonitor,
    VoiceCommand,
    CommandSafetyCriticality,
    ExecutionLocation
)
from voice_assistant.vehicle_control import SimulatedVehicleControl
from voice_assistant.intent_parser import VoiceIntentParser


class MockCloudService:
    """Mock cloud service for demo"""
    
    async def route_to_destination(self, destination: str) -> str:
        """Simulate cloud routing service"""
        await asyncio.sleep(0.2)  # Simulate 200ms cloud latency
        return f"Cloud: Route to {destination} calculated (ETA: 12 min)"
    
    async def find_restaurant(self, cuisine: str):
        """Simulate cloud search service"""
        await asyncio.sleep(0.2)
        restaurants = {
            "italian": ["Mario's", "Pasta Perfetto"],
            "chinese": ["Golden Dragon", "Jade Garden"],
            "mexican": ["Casa Taco", "El Mariachi"]
        }
        nearby = restaurants.get(cuisine, ["Local restaurant"])
        return f"Cloud: Found 3 {cuisine} restaurants: {', '.join(nearby)}"


async def run_demo():
    """Run the hybrid voice assistant demo"""
    
    print("\n" + "="*70)
    print("  HYBRID VOICE ASSISTANT FOR VEHICLE CONTROL - DEMO")
    print("="*70)
    print("\n🎙️  Intelligent edge-cloud routing for real-time vehicle control\n")
    
    # Initialize components
    print("📋 Initializing components...")
    vehicle = SimulatedVehicleControl()
    network = NetworkMonitor()
    cloud_service = MockCloudService()
    
    # Edge executor with simulated vehicle
    edge_executor = EdgeCommandExecutor(vehicle)
    
    # Cloud executor
    cloud_executor = CloudCommandExecutor(cloud_service, vehicle)
    
    # Hybrid router
    router = HybridVoiceRouter(edge_executor, cloud_executor, network)
    
    # Intent parser
    parser = VoiceIntentParser(use_llm_fallback=False)
    
    print("✅ Components initialized\n")
    
    # Define test scenarios
    test_commands = [
        # Safety-critical (EDGE_ONLY)
        {
            "voice": "Stop the car immediately",
            "description": "Emergency brake - SAFETY CRITICAL",
            "expected_location": ExecutionLocation.EDGE_ONLY
        },
        {
            "voice": "Accelerate to 60 kilometers per hour",
            "description": "Acceleration - SAFETY CRITICAL",
            "expected_location": ExecutionLocation.EDGE_ONLY
        },
        {
            "voice": "Turn left 30 degrees",
            "description": "Steering - SAFETY CRITICAL",
            "expected_location": ExecutionLocation.EDGE_ONLY
        },
        
        # High priority vehicle control (EDGE_PRIMARY)
        {
            "voice": "Turn on hazard lights",
            "description": "Hazard lights - HIGH PRIORITY",
            "expected_location": ExecutionLocation.EDGE_PRIMARY
        },
        {
            "voice": "Set temperature to 22 degrees",
            "description": "Climate control - EDGE_PRIMARY",
            "expected_location": ExecutionLocation.EDGE_PRIMARY
        },
        
        # Complex reasoning (CLOUD_PRIMARY)
        {
            "voice": "Route me to the airport",
            "description": "Route optimization - CLOUD_PRIMARY (complex reasoning)",
            "expected_location": ExecutionLocation.CLOUD_PRIMARY
        },
        {
            "voice": "Find a nearby Italian restaurant",
            "description": "Search & discovery - CLOUD_PRIMARY",
            "expected_location": ExecutionLocation.CLOUD_PRIMARY
        },
    ]
    
    # Scenario 1: Normal network (good connectivity)
    print("\n" + "-"*70)
    print("SCENARIO 1: NORMAL NETWORK (50ms latency, 0% packet loss)")
    print("-"*70)
    
    network.update_metrics(latency_ms=50, packet_loss=0.0)
    results_normal = await execute_commands(parser, router, test_commands[:4])
    
    # Scenario 2: Degraded network (high latency)
    print("\n" + "-"*70)
    print("SCENARIO 2: DEGRADED NETWORK (500ms latency, 5% packet loss)")
    print("-"*70)
    
    network.update_metrics(latency_ms=500, packet_loss=0.05)
    results_degraded = await execute_commands(parser, router, test_commands[4:6])
    
    # Scenario 3: Offline network (no connectivity)
    print("\n" + "-"*70)
    print("SCENARIO 3: OFFLINE NETWORK (no connectivity)")
    print("-"*70)
    
    network.update_metrics(latency_ms=10000, packet_loss=1.0)
    network.is_connected = False
    results_offline = await execute_commands(parser, router, [
        {
            "voice": "Accelerate to 80 kilometers per hour",
            "description": "Acceleration during offline",
            "expected_location": ExecutionLocation.EDGE_ONLY
        }
    ])
    
    # Print summary statistics
    print("\n" + "="*70)
    print("  PERFORMANCE SUMMARY")
    print("="*70)
    
    stats = router.get_stats()
    print(f"\n📊 Statistics:")
    print(f"   Total commands processed: {stats['total_commands']}")
    print(f"   Edge executions: {stats['edge_executions']}")
    print(f"   Cloud executions: {stats['cloud_executions']}")
    print(f"   Fallbacks used: {stats['fallbacks_used']}")
    print(f"   Success rate: {stats['success_rate']*100:.1f}%")
    print(f"   Average latency: {stats['avg_latency_ms']:.1f}ms")
    
    # Print routing decisions
    print(f"\n🗺️  Routing Decisions Log:\n")
    for i, decision in enumerate(router.decision_log, 1):
        print(f"   {i}. {decision['intent']}")
        print(f"      Location: {decision['executed_on']}")
        print(f"      Latency: {decision['latency_ms']:.1f}ms")
        print(f"      Success: {'✅' if decision['success'] else '❌'}")
        if decision['fallback']:
            print(f"      Fallback used: ⚠️")
        print()
    
    # Print final vehicle state
    print(f"\n🚗 Final Vehicle State:")
    state = vehicle.get_state()
    print(f"   Speed: {state['speed']:.1f} km/h")
    print(f"   Steering: {state['steering_angle']:.1f}°")
    print(f"   Temperature: {state['temperature']:.1f}°C")
    print(f"   Volume: {state['volume']}%")
    print(f"   Hazard lights: {'ON' if state['hazard_lights'] else 'OFF'}")
    print(f"   Total commands executed: {state['commands_executed']}")
    
    print("\n" + "="*70)
    print("  KEY INSIGHTS")
    print("="*70)
    print("""
✅ Safety-critical commands (brake, accelerate, steer) → Always edge
✅ Latency-aware routing: High RTT pushes commands to edge
✅ Network-aware fallback: Seamless transition when cloud unavailable
✅ Hybrid approach: Best of both worlds - edge speed + cloud intelligence
✅ Graceful degradation: System works even with poor connectivity

🎯 Benefits for Vehicle Control:
   • <50ms response for safety-critical commands (edge execution)
   • Cloud intelligence for complex reasoning (routing, search)
   • Automatic fallback ensures commands succeed
   • Real-time awareness of network conditions
    """)
    
    print("="*70 + "\n")


async def execute_commands(parser, router, commands: List[dict]):
    """Execute list of commands and report results"""
    
    results = []
    
    for cmd_spec in commands:
        voice_text = cmd_spec["voice"]
        description = cmd_spec["description"]
        
        print(f"\n🎤 Voice Input: \"{voice_text}\"")
        print(f"   📝 Description: {description}")
        
        # Parse voice to intent
        command = parser.parse(voice_text)
        if not command:
            print(f"   ❌ Failed to parse command")
            continue
        
        print(f"   ✓ Parsed intent: {command.intent}")
        print(f"   ✓ Confidence: {command.confidence*100:.0f}%")
        print(f"   ✓ Criticality: {command.criticality.name}")
        
        # Execute with hybrid routing
        result = await router.execute_with_fallback(command)
        
        # Report result
        print(f"   ✓ Executed on: {result.executed_on.value}")
        print(f"   ✓ Latency: {result.latency_ms:.1f}ms")
        print(f"   ✓ Response: {result.response}")
        
        if result.fallback_used:
            print(f"   ⚠️  Fallback was used")
        
        results.append(result)
    
    return results


def show_architecture_diagram():
    """Display system architecture"""
    
    diagram = """
╔════════════════════════════════════════════════════════════════════════╗
║                 HYBRID VOICE ASSISTANT ARCHITECTURE                    ║
╚════════════════════════════════════════════════════════════════════════╝

┌──────────────┐
│  Voice Input │  "Accelerate to 80 km/h"
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────┐
│  Intent Parser                  │
│  (Fast pattern matching)        │
└──────┬────────────────────┬─────┘
       │                    │
       ▼ (Safety-critical)  ▼ (Complex reasoning)
       │                    │
   ┌───┴──────────┐  ┌──────┴──────────┐
   │ Edge Executor│  │ Cloud Executor  │
   │ (Jetson Nano)│  │ (Google Cloud)  │
   │              │  │                 │
   │ • Brake      │  │ • Route finding │
   │ • Accelerate │  │ • Search        │
   │ • Steering   │  │ • Analysis      │
   │              │  │                 │
   │ <50ms RTT    │  │ 200-500ms RTT   │
   └───┬──────────┘  └────────┬────────┘
       │                      │
       └──────────┬───────────┘
                  │
    ┌─────────────▼──────────────┐
    │ Hybrid Router              │
    │ • Network monitoring       │
    │ • Latency-aware decisions  │
    │ • Automatic fallback       │
    │ • Performance tracking     │
    └─────────────┬──────────────┘
                  │
                  ▼
         ┌─────────────────────┐
         │ Vehicle Control     │
         │ (KUKSA VSS)         │
         │                     │
         │ • Steering wheel    │
         │ • Acceleration      │
         │ • Braking system    │
         │ • Climate control   │
         └─────────────────────┘

════════════════════════════════════════════════════════════════════════

ROUTING LOGIC:

1. Safety-Critical (Brake, Accelerate, Steer)
   → EDGE_ONLY (no latency, always available)

2. Vehicle Control (Lights, Temperature)
   → EDGE_PRIMARY (prefer edge, fallback to cloud)

3. Simple Actions (Volume, Climate)
   → EDGE_PRIMARY (but acceptable on cloud)

4. Complex Reasoning (Route, Search, Analysis)
   → CLOUD_PRIMARY (needs LLM/APIs, edge fallback if offline)

5. Network Degradation
   → Automatically shift cloud commands to edge
   → Increase edge-only execution ratio
"""
    
    print(diagram)


if __name__ == "__main__":
    print("\n")
    show_architecture_diagram()
    
    # Run demo
    asyncio.run(run_demo())
