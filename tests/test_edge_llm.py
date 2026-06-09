"""Property-based tests for the Edge LLM client.

Property 11: Edge LLM API contract consistency — for any prompt and
target config (lmstudio/jetson), verify identical request structure.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from speechless.edge.edge_llm import EdgeLLMClient, EdgeLLMConfig


class TestEdgeLLMAPIContract:
    """Property 11: API contract is identical regardless of target."""

    @given(
        user_message=st.text(min_size=1, max_size=200),
        history_messages=st.lists(
            st.fixed_dictionaries({
                "role": st.sampled_from(["user", "assistant"]),
                "content": st.text(min_size=1, max_size=100),
            }),
            max_size=5,
        ),
    )
    @settings(max_examples=100, deadline=None)
    def test_request_structure_identical_across_targets(
        self, user_message: str, history_messages: list
    ):
        """Request messages are identical for lmstudio and jetson targets."""
        lmstudio_config = EdgeLLMConfig(target="lmstudio")
        jetson_config = EdgeLLMConfig(target="jetson")

        lmstudio_client = EdgeLLMClient(lmstudio_config)
        jetson_client = EdgeLLMClient(jetson_config)

        lm_messages = lmstudio_client.build_request_messages(history_messages, user_message)
        jetson_messages = jetson_client.build_request_messages(history_messages, user_message)

        assert lm_messages == jetson_messages

    @given(
        user_message=st.text(min_size=1, max_size=200),
        history_messages=st.lists(
            st.fixed_dictionaries({
                "role": st.sampled_from(["user", "assistant"]),
                "content": st.text(min_size=1, max_size=100),
            }),
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_messages_start_with_system_prompt(self, user_message: str, history_messages: list):
        """Request messages always start with a system prompt."""
        config = EdgeLLMConfig(target="lmstudio")
        client = EdgeLLMClient(config)
        messages = client.build_request_messages(history_messages, user_message)

        assert messages[0]["role"] == "system"
        assert len(messages[0]["content"]) > 0

    @given(
        user_message=st.text(min_size=1, max_size=200),
        history_messages=st.lists(
            st.fixed_dictionaries({
                "role": st.sampled_from(["user", "assistant"]),
                "content": st.text(min_size=1, max_size=100),
            }),
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_messages_end_with_user_message(self, user_message: str, history_messages: list):
        """Request messages always end with the user's new message."""
        config = EdgeLLMConfig(target="lmstudio")
        client = EdgeLLMClient(config)
        messages = client.build_request_messages(history_messages, user_message)

        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == user_message

    @given(
        user_message=st.text(min_size=1, max_size=200),
        history_messages=st.lists(
            st.fixed_dictionaries({
                "role": st.sampled_from(["user", "assistant"]),
                "content": st.text(min_size=1, max_size=100),
            }),
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_messages_length_correct(self, user_message: str, history_messages: list):
        """Total messages = 1 (system) + history + 1 (user)."""
        config = EdgeLLMConfig(target="lmstudio")
        client = EdgeLLMClient(config)
        messages = client.build_request_messages(history_messages, user_message)

        expected_length = 1 + len(history_messages) + 1
        assert len(messages) == expected_length

    def test_lmstudio_base_url(self):
        """LM Studio config uses localhost URL."""
        config = EdgeLLMConfig(target="lmstudio")
        client = EdgeLLMClient(config)
        assert client.client.base_url.host == "localhost"

    def test_jetson_base_url(self):
        """Jetson config uses jetson-device URL."""
        config = EdgeLLMConfig(target="jetson")
        client = EdgeLLMClient(config)
        assert "jetson" in str(client.client.base_url)
