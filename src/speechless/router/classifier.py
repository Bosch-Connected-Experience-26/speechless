"""Command classification and routing.

Classifies transcribed text as either a vehicle control command or an
informational query using keyword-based scoring. Designed for sub-100ms
latency — no LLM call, pure keyword matching.

Routing logic:
    - High confidence vehicle keyword match → "edge" (local Vehicle Controller)
    - Low/no vehicle keyword match → "cloud" (AWS Bedrock)
    - Ambiguous/uncertain → "cloud" (safe fallback for richer answers)

When the system is OFFLINE, the pipeline orchestrator overrides the "cloud"
routing and sends everything to the Edge LLM instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommandCategory(Enum):
    """Classification category for a transcribed command."""

    VEHICLE_CONTROL = "vehicle_control"
    INFORMATIONAL = "informational"


@dataclass
class ClassificationResult:
    """Result of command classification."""

    category: CommandCategory
    confidence: float  # 0.0 to 1.0
    matched_keywords: list[str]


class CommandClassifier:
    """Classifies transcribed text as vehicle control or informational.

    Uses a static keyword set for fast, deterministic classification.
    The confidence score is derived from keyword match density relative
    to the input text length.

    Args:
        confidence_threshold: Minimum confidence to classify as vehicle control.
            Commands below this threshold default to informational/cloud routing.
    """

    VEHICLE_KEYWORDS: set[str] = {
        # HVAC
        "temperature", "heat", "cool", "ac", "hvac", "warm", "cold",
        "warmer", "cooler", "heating", "cooling", "climate",
        # Windows
        "window", "windows",
        # Doors/Locks
        "lock", "unlock", "door", "doors",
        # Lights
        "light", "lights", "headlights", "headlight", "interior",
        # Actions
        "open", "close", "set", "increase", "decrease",
        # Compound triggers (split into individual tokens for matching)
        "turn",
    }

    # Multi-word phrases that strongly indicate vehicle control
    VEHICLE_PHRASES: list[str] = [
        "turn on",
        "turn off",
        "set temperature",
        "open window",
        "close window",
        "lock door",
        "unlock door",
        "turn on lights",
        "turn off lights",
        "roll down",
        "roll up",
    ]

    def __init__(self, confidence_threshold: float = 0.6):
        self.confidence_threshold = confidence_threshold

    def classify(self, text: str) -> ClassificationResult:
        """Classify text into vehicle control or informational category.

        Args:
            text: Transcribed text from the Speech Engine.

        Returns:
            ClassificationResult with category, confidence, and matched keywords.
        """
        if not text or not text.strip():
            return ClassificationResult(
                category=CommandCategory.INFORMATIONAL,
                confidence=1.0,
                matched_keywords=[],
            )

        text_lower = text.lower().strip()
        words = set(text_lower.split())

        # Check single-word keyword matches
        keyword_matches = words.intersection(self.VEHICLE_KEYWORDS)

        # Check phrase matches (boost confidence)
        phrase_matches = [
            phrase for phrase in self.VEHICLE_PHRASES if phrase in text_lower
        ]

        # Score: keyword density + phrase bonus
        word_count = max(len(text_lower.split()), 1)
        keyword_score = len(keyword_matches) / word_count
        phrase_bonus = len(phrase_matches) * 0.3

        confidence = min(1.0, (keyword_score * 3) + phrase_bonus)

        matched = list(keyword_matches) + phrase_matches

        if confidence >= self.confidence_threshold:
            return ClassificationResult(
                category=CommandCategory.VEHICLE_CONTROL,
                confidence=confidence,
                matched_keywords=matched,
            )

        # Low confidence → informational (safe fallback)
        return ClassificationResult(
            category=CommandCategory.INFORMATIONAL,
            confidence=1.0 - confidence,
            matched_keywords=matched,
        )

    def route(self, result: ClassificationResult) -> str:
        """Return the routing destination based on classification.

        Args:
            result: A ClassificationResult from classify().

        Returns:
            "edge" for vehicle control, "cloud" for informational queries.
        """
        if result.category == CommandCategory.VEHICLE_CONTROL:
            return "edge"
        return "cloud"
