"""
Hybrid Edge-Cloud Voice Router
================================

Intelligently routes voice commands between edge (Jetson Nano) and cloud systems
based on latency requirements, network conditions, and command safety criticality.

Architecture:
- Safety-Critical Commands (steering, braking) → Edge (instant local execution)
- Real-Time Commands (turn signals, climate) → Edge with cloud fallback
- Complex Reasoning (route optimization) → Cloud with edge caching
- Voice Recognition → Parallel edge+cloud with fastest-wins strategy
"""

import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple, Optional, Callable
import threading
from queue import Queue, Empty
import json

logger = logging.getLogger(__name__)


class CommandSafetyCriticality(Enum):
    """Safety classification for vehicle commands"""
    CRITICAL = 1  # Must execute on edge (steering, braking)
    HIGH = 2      # Prefer edge, can fallback to cloud
    MEDIUM = 3    # Cloud preferred, edge fallback for low latency
    LOW = 4       # Cloud only, can be delayed


class ExecutionLocation(Enum):
    """Where command should execute"""
    EDGE_ONLY = "edge_only"
    CLOUD_ONLY = "cloud_only"
    EDGE_PRIMARY = "edge_primary"
    CLOUD_PRIMARY = "cloud_primary"
    PARALLEL = "parallel"


@dataclass
class VoiceCommand:
    """Parsed voice command with metadata"""
    raw_text: str
    intent: str  # "accelerate", "turn_left", "route_to_destination", "play_music"
    parameters: Dict
    criticality: CommandSafetyCriticality
    timestamp: float
    confidence: float  # 0.0-1.0 from voice recognition
    request_id: str


@dataclass
class ExecutionResult:
    """Result from command execution"""
    success: bool
    executed_on: ExecutionLocation
    latency_ms: float
    response: str
    error: Optional[str] = None
    fallback_used: bool = False


class NetworkMonitor:
    """Monitor network conditions for latency/reliability decisions"""
    
    def __init__(self):
        self.latency_ms = 50  # Assume 50ms cloud latency
        self.packet_loss = 0.0  # 0-1.0
        self.bandwidth_mbps = 10.0
        self.is_connected = True
    
    def update_metrics(self, latency_ms: float, packet_loss: float):
        """Update network metrics from periodic pings"""
        self.latency_ms = latency_ms
        self.packet_loss = packet_loss
        self.is_connected = latency_ms < 10000 and packet_loss < 0.5
    
    def is_reliable_for_cloud(self) -> bool:
        """Cloud execution viable?"""
        return self.is_connected and self.packet_loss < 0.1
    
    def estimated_round_trip_ms(self) -> float:
        """Estimated RTT for cloud call"""
        if not self.is_connected:
            return 10000  # Effectively infinite
        return self.latency_ms


class EdgeCommandExecutor:
    """Execute safety-critical commands locally on Jetson Nano"""
    
    def __init__(self, vehicle_interface):
        self.vehicle = vehicle_interface
        self.execution_latencies = {}
    
    def can_execute(self, command: VoiceCommand) -> bool:
        """Check if edge can execute this command"""
        edge_capable_intents = {
            "accelerate", "brake", "turn_left", "turn_right",
            "hazard_lights", "change_temperature", "adjust_volume",
            "turn_on_lights", "open_window", "activate_cruise_control"
        }
        return command.intent in edge_capable_intents
    
    async def execute(self, command: VoiceCommand) -> ExecutionResult:
        """Execute command locally with timing"""
        start = time.time()
        
        try:
            result_text = await self._execute_intent(command)
            latency = (time.time() - start) * 1000
            
            self.execution_latencies[command.intent] = latency
            
            return ExecutionResult(
                success=True,
                executed_on=ExecutionLocation.EDGE_PRIMARY,
                latency_ms=latency,
                response=result_text
            )
        except Exception as e:
            logger.error(f"Edge execution failed: {e}")
            return ExecutionResult(
                success=False,
                executed_on=ExecutionLocation.EDGE_PRIMARY,
                latency_ms=(time.time() - start) * 1000,
                response="",
                error=str(e)
            )
    
    async def _execute_intent(self, command: VoiceCommand) -> str:
        """Execute specific vehicle command"""
        intent = command.intent
        params = command.parameters
        
        if intent == "accelerate":
            await self.vehicle.accelerate(params.get("speed", 10))
            return f"Accelerating to {params.get('speed', 10)} km/h"
        
        elif intent == "brake":
            await self.vehicle.brake(params.get("force", 0.5))
            return "Braking applied"
        
        elif intent == "turn_left":
            await self.vehicle.turn(angle=params.get("angle", 15))
            return f"Turning left {params.get('angle', 15)} degrees"
        
        elif intent == "turn_right":
            await self.vehicle.turn(angle=-params.get("angle", 15))
            return f"Turning right {params.get('angle', 15)} degrees"
        
        elif intent == "hazard_lights":
            await self.vehicle.hazard_lights(True)
            return "Hazard lights activated"
        
        elif intent == "change_temperature":
            temp = params.get("temperature", 21)
            await self.vehicle.set_temperature(temp)
            return f"Setting temperature to {temp}°C"
        
        elif intent == "adjust_volume":
            volume = params.get("level", 50)
            await self.vehicle.set_volume(volume)
            return f"Volume set to {volume}%"
        
        else:
            raise ValueError(f"Unknown intent: {intent}")


class CloudCommandExecutor:
    """Execute complex commands via cloud APIs"""
    
    def __init__(self, cloud_client, vehicle_interface):
        self.cloud_client = cloud_client
        self.vehicle = vehicle_interface
    
    def can_execute(self, command: VoiceCommand) -> bool:
        """Check if cloud can execute this command"""
        cloud_capable_intents = {
            "route_to_destination", "find_nearest_restaurant",
            "book_parking", "call_friend", "play_music",
            "get_weather", "translate_text", "summarize_news"
        }
        return command.intent in cloud_capable_intents
    
    async def execute(self, command: VoiceCommand) -> ExecutionResult:
        """Execute command via cloud API"""
        start = time.time()
        
        try:
            # Simulate cloud API call
            result_text = await self._call_cloud_api(command)
            latency = (time.time() - start) * 1000
            
            return ExecutionResult(
                success=True,
                executed_on=ExecutionLocation.CLOUD_PRIMARY,
                latency_ms=latency,
                response=result_text
            )
        except Exception as e:
            logger.error(f"Cloud execution failed: {e}")
            return ExecutionResult(
                success=False,
                executed_on=ExecutionLocation.CLOUD_PRIMARY,
                latency_ms=(time.time() - start) * 1000,
                response="",
                error=str(e)
            )
    
    async def _call_cloud_api(self, command: VoiceCommand) -> str:
        """Call cloud service"""
        intent = command.intent
        params = command.parameters
        
        if intent == "route_to_destination":
            destination = params.get("destination", "unknown")
            # Would call Google Maps API
            return f"Route to {destination} updated. ETA: 12 minutes"
        
        elif intent == "find_nearest_restaurant":
            cuisine = params.get("cuisine", "any")
            # Would call Google Places API
            return f"Found 3 {cuisine} restaurants nearby"
        
        elif intent == "book_parking":
            location = params.get("location", "current")
            # Would call parking service API
            return "Parking space reserved"
        
        else:
            raise ValueError(f"Unknown cloud intent: {intent}")


class HybridVoiceRouter:
    """
    Intelligent router that decides where to execute voice commands.
    
    Decision Logic:
    1. Classify command safety criticality
    2. Check if edge or cloud can execute
    3. Consider network conditions
    4. Choose execution location using latency-aware strategy
    5. Execute with fallback options
    """
    
    def __init__(self, edge_executor: EdgeCommandExecutor,
                 cloud_executor: CloudCommandExecutor,
                 network_monitor: NetworkMonitor):
        self.edge = edge_executor
        self.cloud = cloud_executor
        self.network = network_monitor
        self.command_history = []
        self.decision_log = []
    
    def route_command(self, command: VoiceCommand) -> Tuple[ExecutionLocation, str]:
        """
        Determine optimal execution location for command.
        
        Returns: (ExecutionLocation, reasoning)
        """
        reasoning = []
        
        # Step 1: Safety criticality rules
        if command.criticality == CommandSafetyCriticality.CRITICAL:
            reasoning.append(f"Safety-critical intent ({command.intent}) → EDGE_ONLY")
            return ExecutionLocation.EDGE_ONLY, " → ".join(reasoning)
        
        # Step 2: Check edge capability
        edge_capable = self.edge.can_execute(command)
        cloud_capable = self.cloud.can_execute(command)
        
        if edge_capable and not cloud_capable:
            reasoning.append(f"Only edge capable for {command.intent}")
            return ExecutionLocation.EDGE_PRIMARY, " → ".join(reasoning)
        
        if cloud_capable and not edge_capable:
            reasoning.append(f"Only cloud capable for {command.intent}")
            return ExecutionLocation.CLOUD_PRIMARY, " → ".join(reasoning)
        
        # Step 3: Both capable - use latency-aware strategy
        if edge_capable and cloud_capable:
            edge_latency = self.edge.execution_latencies.get(command.intent, 50)
            cloud_rtt = self.network.estimated_round_trip_ms()
            
            reasoning.append(f"Edge latency: {edge_latency:.0f}ms")
            reasoning.append(f"Cloud RTT: {cloud_rtt:.0f}ms")
            
            # If cloud RTT is too high, use edge
            if cloud_rtt > 500:
                reasoning.append("Cloud RTT too high (>500ms) → EDGE_PRIMARY")
                return ExecutionLocation.EDGE_PRIMARY, " → ".join(reasoning)
            
            # If network unreliable, prefer edge
            if not self.network.is_reliable_for_cloud():
                reasoning.append("Network unreliable → EDGE_PRIMARY")
                return ExecutionLocation.EDGE_PRIMARY, " → ".join(reasoning)
            
            # Otherwise use parallel execution (fastest-wins)
            reasoning.append("Both viable, using parallel execution")
            return ExecutionLocation.PARALLEL, " → ".join(reasoning)
        
        # Step 4: Only high-level reasoning (cloud-only)
        reasoning.append(f"Complex reasoning required for {command.intent}")
        return ExecutionLocation.CLOUD_PRIMARY, " → ".join(reasoning)
    
    async def execute_with_fallback(self, command: VoiceCommand) -> ExecutionResult:
        """Execute command with intelligent fallback strategy"""
        
        # Determine execution location
        location, reasoning = self.route_command(command)
        logger.info(f"[{command.request_id}] Routing decision: {reasoning}")
        
        # Execute based on routing decision
        if location == ExecutionLocation.EDGE_ONLY:
            result = await self.edge.execute(command)
        
        elif location == ExecutionLocation.CLOUD_ONLY:
            result = await self.cloud.execute(command)
            # Fallback to edge if cloud fails
            if not result.success and self.edge.can_execute(command):
                logger.info(f"Cloud failed, falling back to edge")
                result = await self.edge.execute(command)
                result.fallback_used = True
        
        elif location == ExecutionLocation.EDGE_PRIMARY:
            result = await self.edge.execute(command)
            # Fallback to cloud if edge fails
            if not result.success and self.cloud.can_execute(command):
                logger.info(f"Edge failed, falling back to cloud")
                result = await self.cloud.execute(command)
                result.fallback_used = True
        
        elif location == ExecutionLocation.CLOUD_PRIMARY:
            result = await self.cloud.execute(command)
            # Fallback to edge if cloud fails
            if not result.success and self.edge.can_execute(command):
                logger.info(f"Cloud failed, falling back to edge")
                result = await self.edge.execute(command)
                result.fallback_used = True
        
        elif location == ExecutionLocation.PARALLEL:
            # Race both executors, return fastest successful result
            result = await self._execute_parallel(command)
        
        # Log decision and result
        self.command_history.append(command)
        self.decision_log.append({
            "request_id": command.request_id,
            "intent": command.intent,
            "decision": location.value,
            "reasoning": reasoning,
            "success": result.success,
            "latency_ms": result.latency_ms,
            "executed_on": result.executed_on.value,
            "fallback": result.fallback_used
        })
        
        return result
    
    async def _execute_parallel(self, command: VoiceCommand) -> ExecutionResult:
        """Execute both edge and cloud in parallel, return fastest success"""
        results = {}
        
        try:
            # Start both executions
            edge_task = self.edge.execute(command)
            cloud_task = self.cloud.execute(command)
            
            # Wait for first successful result (simplified - would use asyncio.wait)
            import asyncio
            done, pending = await asyncio.wait(
                [edge_task, cloud_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Get first result
            for task in done:
                result = task.result()
                if result.success:
                    return result
            
            # If first failed, try second
            for task in pending:
                result = await task
                if result.success:
                    return result
            
            # Both failed, return edge result
            return await edge_task
        
        except Exception as e:
            logger.error(f"Parallel execution error: {e}")
            return await self.edge.execute(command)
    
    def get_stats(self) -> Dict:
        """Return routing statistics"""
        return {
            "total_commands": len(self.command_history),
            "edge_executions": sum(1 for d in self.decision_log if "edge" in d.get("executed_on", "")),
            "cloud_executions": sum(1 for d in self.decision_log if "cloud" in d.get("executed_on", "")),
            "fallbacks_used": sum(1 for d in self.decision_log if d.get("fallback", False)),
            "success_rate": sum(1 for d in self.decision_log if d.get("success", False)) / max(1, len(self.decision_log)),
            "avg_latency_ms": sum(d.get("latency_ms", 0) for d in self.decision_log) / max(1, len(self.decision_log))
        }
