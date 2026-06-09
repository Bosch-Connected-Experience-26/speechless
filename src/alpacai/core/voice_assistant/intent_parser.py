"""
Voice Intent Parser
===================

Converts raw voice text to structured intents with parameters.
Uses simple rule-based patterns (for speed) + optional cloud LLM fallback (for complexity).
"""

import re
import logging
from typing import Tuple, Dict, Optional
from dataclasses import dataclass
import json
import time
import uuid

from .hybrid_router import VoiceCommand, CommandSafetyCriticality

logger = logging.getLogger(__name__)


@dataclass
class IntentPattern:
    """Pattern for matching voice commands"""
    intent: str
    patterns: list  # List of regex patterns
    safety_criticality: CommandSafetyCriticality
    parameter_extractor: callable  # Function to extract parameters


class VoiceIntentParser:
    """Parse voice commands into structured intents"""
    
    def __init__(self, use_llm_fallback: bool = False):
        """
        Args:
            use_llm_fallback: If True, use LLM for unmatched commands
        """
        self.use_llm_fallback = use_llm_fallback
        self.llm_client = None
        self.patterns = self._initialize_patterns()
        self.confidence_scores = {}
    
    def _initialize_patterns(self) -> Dict[str, IntentPattern]:
        """Define voice command patterns"""
        return {
            # Safety-critical commands
            "brake": IntentPattern(
                intent="brake",
                patterns=[
                    r"(\b(brake|stop|stop the car)\b)",
                    r"(\bquick stop\b)",
                    r"(\bemergency.*stop\b)"
                ],
                safety_criticality=CommandSafetyCriticality.CRITICAL,
                parameter_extractor=self._extract_brake_params
            ),
            "accelerate": IntentPattern(
                intent="accelerate",
                patterns=[
                    r"(accelerate|speed up|go faster)",
                    r"(\bgo\b.*\b(faster|speed)\b)",
                    r"(\b(\d+)\s*(?:km|kmh|km/h|kph|mph)\b)",
                ],
                safety_criticality=CommandSafetyCriticality.CRITICAL,
                parameter_extractor=self._extract_speed_params
            ),
            "turn_left": IntentPattern(
                intent="turn_left",
                patterns=[
                    r"(turn left|steer left|veer left)",
                    r"(left.*turn|left.*degrees)",
                ],
                safety_criticality=CommandSafetyCriticality.CRITICAL,
                parameter_extractor=self._extract_angle_params
            ),
            "turn_right": IntentPattern(
                intent="turn_right",
                patterns=[
                    r"(turn right|steer right|veer right)",
                    r"(right.*turn|right.*degrees)",
                ],
                safety_criticality=CommandSafetyCriticality.CRITICAL,
                parameter_extractor=self._extract_angle_params
            ),
            
            # High priority - vehicle control
            "hazard_lights": IntentPattern(
                intent="hazard_lights",
                patterns=[
                    r"(hazard|hazard lights|turn on hazards|activate hazards)",
                    r"(emergency lights)",
                ],
                safety_criticality=CommandSafetyCriticality.HIGH,
                parameter_extractor=lambda text: {"enable": True}
            ),
            "change_temperature": IntentPattern(
                intent="change_temperature",
                patterns=[
                    r"(set temperature|change temperature|make it warmer|make it cooler)",
                    r"(set.*(?:ac|heating|climate))",
                    r"(temperature.*(\d+).*degrees|(\d+).*degrees)",
                ],
                safety_criticality=CommandSafetyCriticality.MEDIUM,
                parameter_extractor=self._extract_temperature_params
            ),
            "adjust_volume": IntentPattern(
                intent="adjust_volume",
                patterns=[
                    r"(turn.*(?:volume|music|sound)|adjust volume)",
                    r"(volume.*(?:up|down|higher|lower))",
                    r"((?:up|down|louder|softer|higher|lower).*(?:volume|music))",
                ],
                safety_criticality=CommandSafetyCriticality.LOW,
                parameter_extractor=self._extract_volume_params
            ),
            
            # Complex reasoning - cloud
            "route_to_destination": IntentPattern(
                intent="route_to_destination",
                patterns=[
                    r"((?:route|navigate|drive|go).*(?:to|towards)\s+[a-z\s]+)",
                    r"(take me to|directions to)",
                ],
                safety_criticality=CommandSafetyCriticality.MEDIUM,
                parameter_extractor=self._extract_destination_params
            ),
            "find_nearest_restaurant": IntentPattern(
                intent="find_nearest_restaurant",
                patterns=[
                    r"(find.*(?:restaurant|food|dining|cafe))",
                    r"(where.*(?:restaurant|food))",
                ],
                safety_criticality=CommandSafetyCriticality.LOW,
                parameter_extractor=self._extract_cuisine_params
            ),
        }
    
    def parse(self, voice_text: str) -> Optional[VoiceCommand]:
        """
        Parse voice text into structured command.
        
        Returns: VoiceCommand or None if unable to parse
        """
        voice_text_lower = voice_text.lower().strip()
        logger.info(f"Parsing voice input: '{voice_text}'")
        
        # Step 1: Try pattern matching (fast, local)
        for pattern_key, pattern in self.patterns.items():
            for regex_pattern in pattern.patterns:
                if re.search(regex_pattern, voice_text_lower, re.IGNORECASE):
                    confidence = 0.95 if len(pattern.patterns) == 1 else 0.85
                    params = pattern.parameter_extractor(voice_text_lower)
                    
                    command = VoiceCommand(
                        raw_text=voice_text,
                        intent=pattern.intent,
                        parameters=params,
                        criticality=pattern.safety_criticality,
                        timestamp=time.time(),
                        confidence=confidence,
                        request_id=str(uuid.uuid4())[:8]
                    )
                    
                    logger.info(f"Matched intent: {pattern.intent} (confidence: {confidence})")
                    self.confidence_scores[pattern.intent] = confidence
                    return command
        
        # Step 2: LLM fallback for unmatched commands (if enabled)
        if self.use_llm_fallback and self.llm_client:
            logger.info("No pattern match, trying LLM fallback...")
            return self._parse_with_llm(voice_text)
        
        logger.warning(f"Unable to parse voice input: '{voice_text}'")
        return None
    
    def _extract_speed_params(self, text: str) -> Dict:
        """Extract speed parameter from text"""
        match = re.search(r'(\d+)\s*(?:km|kmh|km/h|kph|mph)', text)
        speed = float(match.group(1)) if match else 30.0
        return {"speed": speed}
    
    def _extract_angle_params(self, text: str) -> Dict:
        """Extract steering angle parameter"""
        match = re.search(r'(\d+)\s*(?:degree|degrees|deg)', text)
        angle = float(match.group(1)) if match else 15.0
        return {"angle": angle}
    
    def _extract_brake_params(self, text: str) -> Dict:
        """Extract brake force parameter"""
        # Detect emergency/hard braking
        if "emergency" in text or "hard" in text or "quick" in text:
            force = 1.0
        else:
            force = 0.5
        return {"force": force}
    
    def _extract_temperature_params(self, text: str) -> Dict:
        """Extract temperature from text"""
        match = re.search(r'(\d+)\s*(?:degree|°|c|celsius|f|fahrenheit)', text)
        temp = float(match.group(1)) if match else 21.0
        
        # Adjust for cooler/warmer preferences
        if "cool" in text or "cold" in text:
            temp = max(16, temp - 3)
        elif "warm" in text or "hot" in text:
            temp = min(32, temp + 3)
        
        return {"temperature": temp}
    
    def _extract_volume_params(self, text: str) -> Dict:
        """Extract volume adjustment"""
        match = re.search(r'(\d+)', text)
        if match:
            level = int(match.group(1))
        elif "up" in text or "louder" in text or "higher" in text:
            level = 70
        elif "down" in text or "softer" in text or "lower" in text or "mute" in text:
            level = 20
        else:
            level = 50
        
        return {"level": max(0, min(100, level))}
    
    def _extract_destination_params(self, text: str) -> Dict:
        """Extract destination from route commands"""
        # Extract location after "to"
        match = re.search(r'(?:to|towards)\s+(.+?)(?:\.|$)', text)
        destination = match.group(1).strip() if match else "unknown"
        return {"destination": destination}
    
    def _extract_cuisine_params(self, text: str) -> Dict:
        """Extract cuisine preference"""
        cuisines = ["italian", "chinese", "mexican", "indian", "japanese", "thai", "french"]
        for cuisine in cuisines:
            if cuisine in text:
                return {"cuisine": cuisine}
        return {"cuisine": "any"}
    
    def _parse_with_llm(self, voice_text: str) -> Optional[VoiceCommand]:
        """
        Use LLM to parse complex commands.
        
        Example: "Tell me a joke" → intent="play_music", "Call my mom" → intent="call_friend"
        """
        if not self.llm_client:
            return None
        
        try:
            prompt = f"""Parse this voice command and extract the intent and parameters.
            
Voice: "{voice_text}"

Respond in JSON format:
{{
    "intent": "one of: brake, accelerate, turn_left, turn_right, hazard_lights, change_temperature, adjust_volume, route_to_destination, find_nearest_restaurant, call_friend, play_music",
    "parameters": {{}},
    "safety_criticality": "CRITICAL|HIGH|MEDIUM|LOW",
    "confidence": 0.0-1.0
}}
"""
            
            # Would call LLM here
            logger.info("LLM parsing not implemented in demo")
            return None
        
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return None
    
    def get_confidence_history(self) -> Dict:
        """Get historical confidence scores"""
        return self.confidence_scores.copy()
