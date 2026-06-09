"""Property-based tests for the Command Classifier.

Property 2: Classification completeness — for any non-empty text,
classifier always returns a valid ClassificationResult (never None).

Property 3: Routing correctness — VEHICLE_CONTROL → "edge",
INFORMATIONAL → "cloud".
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from speechless.router.classifier import (
    ClassificationResult,
    CommandCategory,
    CommandClassifier,
)


class TestClassificationCompleteness:
    """Property 2: For any non-empty text, classifier always returns valid result."""

    @given(text=st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_classify_always_returns_result(self, text: str):
        """Classification never returns None for any non-empty input."""
        classifier = CommandClassifier()
        result = classifier.classify(text)
        assert result is not None
        assert isinstance(result, ClassificationResult)

    @given(text=st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_classify_has_valid_category(self, text: str):
        """Classification always returns a valid CommandCategory."""
        classifier = CommandClassifier()
        result = classifier.classify(text)
        assert result.category in (CommandCategory.VEHICLE_CONTROL, CommandCategory.INFORMATIONAL)

    @given(text=st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_classify_has_valid_confidence(self, text: str):
        """Confidence is always between 0 and 1."""
        classifier = CommandClassifier()
        result = classifier.classify(text)
        assert 0.0 <= result.confidence <= 1.0

    @given(text=st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_classify_matched_keywords_is_list(self, text: str):
        """Matched keywords is always a list."""
        classifier = CommandClassifier()
        result = classifier.classify(text)
        assert isinstance(result.matched_keywords, list)


class TestRoutingCorrectness:
    """Property 3: Routing follows classification — VEHICLE_CONTROL → edge, INFORMATIONAL → cloud."""

    @given(text=st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_vehicle_control_routes_to_edge(self, text: str):
        """VEHICLE_CONTROL classification always routes to 'edge'."""
        classifier = CommandClassifier()
        result = classifier.classify(text)
        route = classifier.route(result)
        if result.category == CommandCategory.VEHICLE_CONTROL:
            assert route == "edge"

    @given(text=st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_informational_routes_to_cloud(self, text: str):
        """INFORMATIONAL classification always routes to 'cloud'."""
        classifier = CommandClassifier()
        result = classifier.classify(text)
        route = classifier.route(result)
        if result.category == CommandCategory.INFORMATIONAL:
            assert route == "cloud"

    def test_explicit_vehicle_command(self):
        """Known vehicle commands route to edge."""
        classifier = CommandClassifier()
        result = classifier.classify("set temperature to 22")
        assert classifier.route(result) == "edge"

    def test_explicit_informational_query(self):
        """Known informational queries route to cloud."""
        classifier = CommandClassifier()
        result = classifier.classify("what is the weather today in Paris")
        assert classifier.route(result) == "cloud"

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0),
        keywords=st.lists(st.text(min_size=1, max_size=20), max_size=5),
    )
    @settings(max_examples=100)
    def test_route_deterministic_from_category(self, confidence: float, keywords: list):
        """Route is determined solely by category, not confidence."""
        classifier = CommandClassifier()
        # Vehicle control → edge
        vc_result = ClassificationResult(
            category=CommandCategory.VEHICLE_CONTROL,
            confidence=confidence,
            matched_keywords=keywords,
        )
        assert classifier.route(vc_result) == "edge"

        # Informational → cloud
        info_result = ClassificationResult(
            category=CommandCategory.INFORMATIONAL,
            confidence=confidence,
            matched_keywords=keywords,
        )
        assert classifier.route(info_result) == "cloud"
