"""Property-based test for the Speech Engine confidence threshold fallback.

Property 1: Confidence threshold triggers cloud fallback — for any
TranscriptionResult with confidence below threshold, verify cloud fallback.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from speechless.speech.stt_local import TranscriptionResult


class TestConfidenceThresholdFallback:
    """Property 1: Confidence threshold triggers cloud fallback."""

    @given(
        confidence=st.floats(min_value=0.0, max_value=0.69),
        text=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_low_confidence_triggers_fallback(self, confidence: float, text: str):
        """Confidence below threshold should trigger cloud fallback.

        When local STT confidence is below threshold (0.7), the Speech Engine
        should forward to cloud STT.
        """
        from speechless.speech.stt_local import LocalSTT

        # LocalSTT with 0.7 threshold
        stt = LocalSTT.__new__(LocalSTT)
        stt.confidence_threshold = 0.7

        result = TranscriptionResult(text=text, confidence=confidence, source="local")
        assert stt.is_below_threshold(result) is True

    @given(
        confidence=st.floats(min_value=0.7, max_value=1.0),
        text=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_high_confidence_no_fallback(self, confidence: float, text: str):
        """Confidence at or above threshold should NOT trigger fallback."""
        from speechless.speech.stt_local import LocalSTT

        stt = LocalSTT.__new__(LocalSTT)
        stt.confidence_threshold = 0.7

        result = TranscriptionResult(text=text, confidence=confidence, source="local")
        assert stt.is_below_threshold(result) is False

    @given(
        threshold=st.floats(min_value=0.1, max_value=0.9),
        confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=200)
    def test_threshold_comparison_consistent(self, threshold: float, confidence: float):
        """is_below_threshold is True iff confidence < threshold."""
        from speechless.speech.stt_local import LocalSTT

        stt = LocalSTT.__new__(LocalSTT)
        stt.confidence_threshold = threshold

        result = TranscriptionResult(text="test", confidence=confidence, source="local")
        expected = confidence < threshold
        assert stt.is_below_threshold(result) == expected

    def test_cloud_fallback_returns_local_when_unavailable(self):
        """If cloud is unavailable, the local result is returned."""
        from speechless.speech.stt_cloud import CloudSTT

        cloud = CloudSTT(api_key=None)  # No API key → client is None
        local_result = TranscriptionResult(text="hello world", confidence=0.5, source="local")

        import numpy as np
        audio = np.zeros(16000, dtype=np.float32)
        result = cloud.fallback_transcribe(audio, local_result)

        # Should return the local result when cloud is unavailable
        assert result.text == "hello world"
        assert result.source == "local"
        assert result.confidence == 0.5
