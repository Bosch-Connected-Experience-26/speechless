"""
Vehicle Control Interface
==========================

Abstraction layer for vehicle commands that works with both simulation and real KUKSA.
Supports both async and sync execution patterns.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


class VehicleState(Enum):
    """Vehicle state constants"""
    IDLE = "idle"
    MOVING = "moving"
    EMERGENCY = "emergency"
    ERROR = "error"


class VehicleCommandInterface(ABC):
    """Abstract interface for vehicle commands"""
    
    @abstractmethod
    async def accelerate(self, speed_kmh: float) -> Dict[str, Any]:
        """Accelerate to target speed"""
        pass
    
    @abstractmethod
    async def brake(self, force: float = 0.5) -> Dict[str, Any]:
        """Apply brakes with force 0.0-1.0"""
        pass
    
    @abstractmethod
    async def turn(self, angle: float) -> Dict[str, Any]:
        """Turn steering wheel by angle (-180 to +180)"""
        pass
    
    @abstractmethod
    async def hazard_lights(self, enable: bool) -> Dict[str, Any]:
        """Toggle hazard lights"""
        pass
    
    @abstractmethod
    async def set_temperature(self, celsius: float) -> Dict[str, Any]:
        """Set cabin temperature"""
        pass
    
    @abstractmethod
    async def set_volume(self, level: int) -> Dict[str, Any]:
        """Set audio volume (0-100)"""
        pass


class SimulatedVehicleControl(VehicleCommandInterface):
    """Simulated vehicle for testing and development"""
    
    def __init__(self):
        self.state = VehicleState.IDLE
        self.current_speed = 0.0
        self.steering_angle = 0.0
        self.temperature = 21.0
        self.volume = 50
        self.hazard_lights_on = False
        self.command_count = 0
    
    async def accelerate(self, speed_kmh: float) -> Dict[str, Any]:
        """Simulate acceleration"""
        self.current_speed = min(speed_kmh, 200)  # Max 200 km/h
        self.state = VehicleState.MOVING if speed_kmh > 0 else VehicleState.IDLE
        self.command_count += 1
        
        logger.info(f"[EDGE] Accelerating to {self.current_speed} km/h")
        await asyncio.sleep(0.05)  # Simulate execution time
        
        return {
            "status": "success",
            "current_speed": self.current_speed,
            "state": self.state.value
        }
    
    async def brake(self, force: float = 0.5) -> Dict[str, Any]:
        """Simulate braking"""
        deceleration = force * 50  # km/h reduction
        self.current_speed = max(0, self.current_speed - deceleration)
        self.state = VehicleState.IDLE if self.current_speed == 0 else VehicleState.MOVING
        self.command_count += 1
        
        logger.info(f"[EDGE] Braking with force {force}, new speed: {self.current_speed} km/h")
        await asyncio.sleep(0.05)
        
        return {
            "status": "success",
            "current_speed": self.current_speed,
            "force_applied": force
        }
    
    async def turn(self, angle: float) -> Dict[str, Any]:
        """Simulate steering"""
        self.steering_angle = max(-180, min(180, angle))  # Clamp to valid range
        self.command_count += 1
        
        direction = "left" if angle > 0 else "right"
        logger.info(f"[EDGE] Turning {direction} {abs(angle)} degrees")
        await asyncio.sleep(0.05)
        
        return {
            "status": "success",
            "steering_angle": self.steering_angle
        }
    
    async def hazard_lights(self, enable: bool) -> Dict[str, Any]:
        """Simulate hazard lights"""
        self.hazard_lights_on = enable
        self.command_count += 1
        
        status = "ON" if enable else "OFF"
        logger.info(f"[EDGE] Hazard lights {status}")
        await asyncio.sleep(0.02)
        
        return {
            "status": "success",
            "hazard_lights": self.hazard_lights_on
        }
    
    async def set_temperature(self, celsius: float) -> Dict[str, Any]:
        """Simulate HVAC control"""
        self.temperature = max(16, min(32, celsius))  # Valid range
        self.command_count += 1
        
        logger.info(f"[EDGE] Setting temperature to {self.temperature}°C")
        await asyncio.sleep(0.02)
        
        return {
            "status": "success",
            "temperature": self.temperature
        }
    
    async def set_volume(self, level: int) -> Dict[str, Any]:
        """Simulate audio volume"""
        self.volume = max(0, min(100, level))
        self.command_count += 1
        
        logger.info(f"[EDGE] Setting volume to {self.volume}%")
        await asyncio.sleep(0.02)
        
        return {
            "status": "success",
            "volume": self.volume
        }
    
    def get_state(self) -> Dict[str, Any]:
        """Get current vehicle state"""
        return {
            "speed": self.current_speed,
            "steering_angle": self.steering_angle,
            "temperature": self.temperature,
            "volume": self.volume,
            "hazard_lights": self.hazard_lights_on,
            "state": self.state.value,
            "commands_executed": self.command_count
        }


class KuksaVehicleControl(VehicleCommandInterface):
    """Real vehicle control via KUKSA VSS (Vehicle Signal Specification)"""
    
    def __init__(self, kuksa_host: str = "localhost", kuksa_port: int = 55555):
        self.host = kuksa_host
        self.port = kuksa_port
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize KUKSA client"""
        try:
            from kuksa_client.grpc import VSSClient
            self.client = VSSClient(
                host=self.host,
                port=self.port,
                insecure=True
            )
            logger.info(f"KUKSA client initialized: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to initialize KUKSA client: {e}")
            self.client = None
    
    async def accelerate(self, speed_kmh: float) -> Dict[str, Any]:
        """Send acceleration command via KUKSA"""
        try:
            if self.client:
                self.client.set_current_value(
                    "Vehicle.Speed",
                    speed_kmh
                )
                return {"status": "success", "target_speed": speed_kmh}
            else:
                return {"status": "error", "message": "KUKSA not available"}
        except Exception as e:
            logger.error(f"Accelerate error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def brake(self, force: float = 0.5) -> Dict[str, Any]:
        """Send brake command via KUKSA"""
        try:
            if self.client:
                self.client.set_current_value(
                    "Vehicle.Brake.Pedal.Position",
                    force
                )
                return {"status": "success", "brake_force": force}
            else:
                return {"status": "error", "message": "KUKSA not available"}
        except Exception as e:
            logger.error(f"Brake error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def turn(self, angle: float) -> Dict[str, Any]:
        """Send steering command via KUKSA"""
        try:
            if self.client:
                self.client.set_current_value(
                    "Vehicle.Cabin.SteeringWheel.Angle",
                    angle
                )
                return {"status": "success", "steering_angle": angle}
            else:
                return {"status": "error", "message": "KUKSA not available"}
        except Exception as e:
            logger.error(f"Steering error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def hazard_lights(self, enable: bool) -> Dict[str, Any]:
        """Send hazard lights command via KUKSA"""
        try:
            if self.client:
                self.client.set_current_value(
                    "Vehicle.Body.Lights.Hazard.IsOn",
                    enable
                )
                return {"status": "success", "hazard_lights": enable}
            else:
                return {"status": "error", "message": "KUKSA not available"}
        except Exception as e:
            logger.error(f"Hazard lights error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def set_temperature(self, celsius: float) -> Dict[str, Any]:
        """Set HVAC temperature via KUKSA"""
        try:
            if self.client:
                self.client.set_current_value(
                    "Vehicle.Cabin.HVAC.Station.Row1.Temperature",
                    celsius
                )
                return {"status": "success", "temperature": celsius}
            else:
                return {"status": "error", "message": "KUKSA not available"}
        except Exception as e:
            logger.error(f"Temperature error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def set_volume(self, level: int) -> Dict[str, Any]:
        """Set audio volume via KUKSA"""
        try:
            if self.client:
                self.client.set_current_value(
                    "Vehicle.Cabin.Infotainment.Media.Volume",
                    level
                )
                return {"status": "success", "volume": level}
            else:
                return {"status": "error", "message": "KUKSA not available"}
        except Exception as e:
            logger.error(f"Volume error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_state(self) -> Dict[str, Any]:
        """Get vehicle state from KUKSA"""
        try:
            if not self.client:
                return {"status": "error", "message": "KUKSA not available"}
            
            state = {
                "speed": self.client.get_current_value("Vehicle.Speed"),
                "steering_angle": self.client.get_current_value("Vehicle.Cabin.SteeringWheel.Angle"),
                "temperature": self.client.get_current_value("Vehicle.Cabin.HVAC.Station.Row1.Temperature"),
                "volume": self.client.get_current_value("Vehicle.Cabin.Infotainment.Media.Volume"),
            }
            return state
        except Exception as e:
            logger.error(f"Get state error: {e}")
            return {"status": "error", "message": str(e)}
