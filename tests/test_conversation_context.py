"""Property-based tests for the Conversation Context Manager.

Property 15: Context forwarding on connectivity restoration — for any
N-turn context, verify all N turns forwarded to Bedrock.

Property 16: Offline conversation context accumulation — for K offline
interactions, verify context contains K user+assistant turns.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from speechless.context.conversation import ConversationContext


class TestContextForwarding:
    """Property 15: All accumulated turns forwarded on reconnection."""

    @given(
        turns=st.lists(
            st.tuples(
                st.sampled_from(["user", "assistant"]),
                st.text(min_size=1, max_size=100),
            ),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_all_turns_available_for_forwarding(self, turns: list):
        """All N accumulated turns are available for forwarding to Bedrock."""
        ctx = ConversationContext(max_turns=20)
        for role, content in turns:
            ctx.add_turn(role, content)

        # get_messages_for_bedrock returns all turns for forwarding
        messages = ctx.get_messages_for_bedrock()
        assert len(messages) == len(turns)

        for i, (role, content) in enumerate(turns):
            assert messages[i]["role"] == role
            assert messages[i]["content"] == content

    @given(
        turns=st.lists(
            st.tuples(
                st.sampled_from(["user", "assistant"]),
                st.text(min_size=1, max_size=100),
            ),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_forwarded_messages_in_chronological_order(self, turns: list):
        """Forwarded messages maintain chronological order."""
        ctx = ConversationContext(max_turns=20)
        for role, content in turns:
            ctx.add_turn(role, content)

        messages = ctx.get_messages_for_llm()
        # Should be same order as added
        for i, (role, content) in enumerate(turns):
            assert messages[i]["role"] == role
            assert messages[i]["content"] == content


class TestOfflineConversationAccumulation:
    """Property 16: Offline conversation context accumulation."""

    @given(k=st.integers(min_value=1, max_value=10))
    @settings(max_examples=50)
    def test_k_interactions_produce_2k_turns(self, k: int):
        """K user+assistant interaction pairs produce 2K turns."""
        ctx = ConversationContext(max_turns=40)

        for i in range(k):
            ctx.add_turn("user", f"user message {i}")
            ctx.add_turn("assistant", f"assistant response {i}")

        assert ctx.turn_count == 2 * k

    @given(k=st.integers(min_value=1, max_value=10))
    @settings(max_examples=50)
    def test_kth_request_includes_all_previous(self, k: int):
        """The K+1th request includes all K previous interactions."""
        ctx = ConversationContext(max_turns=40)

        for i in range(k):
            ctx.add_turn("user", f"user message {i}")
            ctx.add_turn("assistant", f"assistant response {i}")

        # Get messages for the next request (would include all K pairs)
        messages = ctx.get_messages_for_llm()
        assert len(messages) == 2 * k

    @given(k=st.integers(min_value=5, max_value=10))
    @settings(max_examples=50)
    def test_supports_minimum_five_follow_ups(self, k: int):
        """Supports at least 5 consecutive follow-up turns."""
        ctx = ConversationContext(max_turns=20)

        for i in range(k):
            ctx.add_turn("user", f"follow-up {i}")
            ctx.add_turn("assistant", f"response {i}")

        assert ctx.turn_count >= 10  # 5 pairs minimum

    def test_max_turns_trimming(self):
        """Excess turns are trimmed (oldest removed first)."""
        ctx = ConversationContext(max_turns=4)

        ctx.add_turn("user", "msg 1")
        ctx.add_turn("assistant", "resp 1")
        ctx.add_turn("user", "msg 2")
        ctx.add_turn("assistant", "resp 2")
        ctx.add_turn("user", "msg 3")  # This should trigger trimming

        assert ctx.turn_count == 4
        messages = ctx.get_messages_for_llm()
        # Oldest turn removed
        assert messages[0]["content"] == "resp 1"

    def test_clear_empties_context(self):
        """Clear removes all turns."""
        ctx = ConversationContext()
        ctx.add_turn("user", "hello")
        ctx.add_turn("assistant", "hi")
        ctx.clear()
        assert ctx.is_empty()
        assert ctx.turn_count == 0

    def test_is_empty_on_new_context(self):
        """New context starts empty."""
        ctx = ConversationContext()
        assert ctx.is_empty()
