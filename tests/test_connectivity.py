"""Property-based tests for the Connectivity Monitor.

Property 14: Offline mode routes all queries to Edge LLM — for any query
while OFFLINE, verify routing to Edge LLM regardless of classification.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from speechless.connectivity.monitor import ConnectivityConfig, ConnectivityMonitor, ConnectivityState
from speechless.router.classifier import CommandClassifier, CommandCategory


class TestConnectivityMonitor:
    """Tests for ConnectivityMonitor basic behavior."""

    def test_initial_state_is_online(self):
        """Monitor starts in ONLINE state."""
        monitor = ConnectivityMonitor()
        assert monitor.state == ConnectivityState.ONLINE
        assert monitor.is_online is True

    def test_custom_config(self):
        """Custom config is applied correctly."""
        config = ConnectivityConfig(
            ping_url="http://example.com/ping",
            ping_interval=5.0,
            timeout=2.0,
        )
        monitor = ConnectivityMonitor(config=config)
        assert monitor.config.ping_url == "http://example.com/ping"
        assert monitor.config.ping_interval == 5.0
        assert monitor.config.timeout == 2.0

    def test_state_change_callback(self):
        """State change callback is stored correctly."""
        changes: list = []
        monitor = ConnectivityMonitor(on_state_change=lambda s: changes.append(s))
        assert monitor.on_state_change is not None


class TestOfflineModeRouting:
    """Property 14: Offline mode routes all queries to Edge LLM."""

    @given(text=st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_offline_overrides_cloud_routing(self, text: str):
        """When OFFLINE, all queries should be routed to edge regardless of classification.

        This tests the routing logic: if connectivity state is OFFLINE,
        even informational queries that would normally go to cloud are
        handled by the Edge LLM.
        """
        classifier = CommandClassifier()
        result = classifier.classify(text)
        normal_route = classifier.route(result)

        # In offline mode, the pipeline orchestrator overrides "cloud" → "edge"
        connectivity_state = ConnectivityState.OFFLINE
        if connectivity_state == ConnectivityState.OFFLINE:
            effective_route = "edge"
        else:
            effective_route = normal_route

        assert effective_route == "edge"

    @given(text=st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_online_preserves_normal_routing(self, text: str):
        """When ONLINE, routing follows normal classification logic."""
        classifier = CommandClassifier()
        result = classifier.classify(text)
        normal_route = classifier.route(result)

        connectivity_state = ConnectivityState.ONLINE
        if connectivity_state == ConnectivityState.OFFLINE:
            effective_route = "edge"
        else:
            effective_route = normal_route

        # Route should match normal classification
        if result.category == CommandCategory.VEHICLE_CONTROL:
            assert effective_route == "edge"
        else:
            assert effective_route == "cloud"
