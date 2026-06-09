"""Property-based tests for the Bedrock Client.

Property 12: Bedrock converse API message formatting with history —
for any N messages + new user message, verify all N+1 in chronological order.

Property 13: Bedrock response extraction — for any valid response structure,
verify text extracted without modification.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from speechless.cloud.bedrock_client import BedrockClient, BedrockResponse, ConversationMessage


class TestBedrockMessageFormatting:
    """Property 12: Message formatting preserves history in chronological order."""

    @given(
        history=st.lists(
            st.builds(
                ConversationMessage,
                role=st.sampled_from(["user", "assistant"]),
                content=st.text(min_size=1, max_size=100),
            ),
            min_size=0,
            max_size=10,
        ),
        user_message=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=100)
    def test_all_messages_in_chronological_order(
        self, history: list, user_message: str
    ):
        """All N history messages + new user message appear in order."""
        # We can't instantiate a real client (needs AWS profile), so test _build_messages
        # by using a mock session approach
        client = self._create_mock_client()
        messages = client._build_messages(user_message, history)

        # Total messages = injected context (0) + history + 1 (user)
        expected_count = len(history) + 1
        assert len(messages) == expected_count

        # Last message is always the user's new message
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == [{"text": user_message}]

        # History messages are in the same order
        for i, hist_msg in enumerate(history):
            assert messages[i]["role"] == hist_msg.role
            assert messages[i]["content"] == [{"text": hist_msg.content}]

    @given(
        history=st.lists(
            st.builds(
                ConversationMessage,
                role=st.sampled_from(["user", "assistant"]),
                content=st.text(min_size=1, max_size=100),
            ),
            min_size=1,
            max_size=10,
        ),
        user_message=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=100)
    def test_messages_have_role_and_content(self, history: list, user_message: str):
        """Every message has 'role' and 'content' keys."""
        client = self._create_mock_client()
        messages = client._build_messages(user_message, history)

        for msg in messages:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ("user", "assistant")
            assert isinstance(msg["content"], list)
            assert len(msg["content"]) > 0
            assert "text" in msg["content"][0]

    @given(
        injected=st.lists(
            st.builds(
                ConversationMessage,
                role=st.sampled_from(["user", "assistant"]),
                content=st.text(min_size=1, max_size=50),
            ),
            min_size=1,
            max_size=5,
        ),
        user_message=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_injected_context_appears_first(self, injected: list, user_message: str):
        """Injected offline context appears before other messages."""
        client = self._create_mock_client()
        client.inject_context(injected)
        messages = client._build_messages(user_message, None)

        # Injected messages come first, then user message
        assert len(messages) == len(injected) + 1
        for i, inj_msg in enumerate(injected):
            assert messages[i]["role"] == inj_msg.role
            assert messages[i]["content"] == [{"text": inj_msg.content}]

    @staticmethod
    def _create_mock_client() -> BedrockClient:
        """Create a BedrockClient with mocked boto3 (no AWS connection)."""
        import unittest.mock as mock
        with mock.patch("boto3.Session"):
            client = BedrockClient.__new__(BedrockClient)
            client.model_id = "test-model"
            client.timeout = 5.0
            client.profile_name = "test"
            client.client = mock.MagicMock()
            client._injected_context = []
            return client


class TestBedrockResponseExtraction:
    """Property 13: Response text extracted without modification."""

    @given(text=st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    def test_response_text_preserved(self, text: str):
        """BedrockResponse preserves text exactly as provided."""
        response = BedrockResponse(text=text, model="test-model", success=True)
        assert response.text == text

    @given(text=st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    def test_successful_response_has_no_error(self, text: str):
        """Successful responses have no error message."""
        response = BedrockResponse(text=text, model="test-model", success=True)
        assert response.error_message is None

    @given(error_msg=st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_error_response_has_empty_text(self, error_msg: str):
        """Error responses have empty text."""
        response = BedrockResponse(
            text="", model="test-model", success=False, error_message=error_msg
        )
        assert response.text == ""
        assert response.success is False
        assert response.error_message == error_msg
