"""Property-based tests for the Intent Parser.

Property 4: For any text with recognized vehicle keyword, verify
non-None VehicleIntent with valid system and action.
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from speechless.edge.intent_parser import (
    Action,
    IntentParser,
    VehicleIntent,
    VehicleSystem,
)


# Strategy: text containing a vehicle keyword
VEHICLE_KEYWORDS = [
    "temperature", "heat", "cool", "ac", "hvac", "warm", "cold",
    "window", "door", "lock", "unlock", "light",
]

vehicle_text = st.one_of(
    *[
        st.tuples(
            st.text(min_size=0, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
            st.just(kw),
            st.text(min_size=0, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
        ).map(lambda parts: f"{parts[0]} {parts[1]} {parts[2]}".strip())
        for kw in VEHICLE_KEYWORDS
    ]
)


class TestIntentParsing:
    """Property 4: Intent parsing extracts system and action."""

    @given(text=vehicle_text)
    @settings(max_examples=200)
    def test_vehicle_keyword_produces_intent(self, text: str):
        """Any text containing a vehicle keyword produces a non-None VehicleIntent."""
        assume(text.strip())  # Skip empty strings
        parser = IntentParser()
        result = parser.parse(text)
        assert result is not None
        assert isinstance(result, VehicleIntent)

    @given(text=vehicle_text)
    @settings(max_examples=200)
    def test_intent_has_valid_system(self, text: str):
        """Parsed intent always has a valid VehicleSystem."""
        assume(text.strip())
        parser = IntentParser()
        result = parser.parse(text)
        if result is not None:
            assert result.system in list(VehicleSystem)

    @given(text=vehicle_text)
    @settings(max_examples=200)
    def test_intent_has_valid_action(self, text: str):
        """Parsed intent always has a valid Action."""
        assume(text.strip())
        parser = IntentParser()
        result = parser.parse(text)
        if result is not None:
            assert result.action in list(Action)

    def test_hvac_parsing(self):
        """HVAC command extracts temperature parameter."""
        parser = IntentParser()
        result = parser.parse("set temperature to 25")
        assert result is not None
        assert result.system == VehicleSystem.HVAC
        assert result.action == Action.SET_TEMPERATURE
        assert result.parameters["temperature"] == 25

    def test_window_open(self):
        """Window open command parsed correctly."""
        parser = IntentParser()
        result = parser.parse("open the window")
        assert result is not None
        assert result.system == VehicleSystem.WINDOWS
        assert result.action == Action.OPEN

    def test_window_close(self):
        """Window close command parsed correctly."""
        parser = IntentParser()
        result = parser.parse("close window")
        assert result is not None
        assert result.system == VehicleSystem.WINDOWS
        assert result.action == Action.CLOSE

    def test_door_lock(self):
        """Door lock command parsed correctly."""
        parser = IntentParser()
        result = parser.parse("lock the doors")
        assert result is not None
        assert result.system == VehicleSystem.DOORS
        assert result.action == Action.LOCK

    def test_door_unlock(self):
        """Door unlock command parsed correctly."""
        parser = IntentParser()
        result = parser.parse("unlock door")
        assert result is not None
        assert result.system == VehicleSystem.DOORS
        assert result.action == Action.UNLOCK

    def test_lights_on(self):
        """Lights on command parsed correctly."""
        parser = IntentParser()
        result = parser.parse("turn on the lights")
        assert result is not None
        assert result.system == VehicleSystem.LIGHTS
        assert result.action == Action.TURN_ON

    def test_lights_off(self):
        """Lights off command parsed correctly."""
        parser = IntentParser()
        result = parser.parse("turn off lights")
        assert result is not None
        assert result.system == VehicleSystem.LIGHTS
        assert result.action == Action.TURN_OFF

    def test_unrecognized_returns_none(self):
        """Unrecognized commands return None."""
        parser = IntentParser()
        result = parser.parse("what is the weather today")
        assert result is None

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        parser = IntentParser()
        assert parser.parse("") is None
        assert parser.parse("   ") is None
