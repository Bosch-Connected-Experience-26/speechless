"""Tests for the retry utility module."""

import time
from unittest.mock import patch

import pytest

from speechless.utils.retry import RetryConfig, compute_backoff_delay, retry_sync


class TestRetryConfig:
    """Tests for RetryConfig defaults and construction."""

    def test_defaults(self):
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.multiplier == 2.0
        assert config.max_delay is None

    def test_custom_values(self):
        config = RetryConfig(max_retries=5, base_delay=0.5, multiplier=3.0, max_delay=10.0)
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.multiplier == 3.0
        assert config.max_delay == 10.0


class TestComputeBackoffDelay:
    """Tests for compute_backoff_delay function."""

    def test_first_attempt(self):
        config = RetryConfig(base_delay=1.0, multiplier=2.0)
        assert compute_backoff_delay(0, config) == 1.0

    def test_second_attempt(self):
        config = RetryConfig(base_delay=1.0, multiplier=2.0)
        assert compute_backoff_delay(1, config) == 2.0

    def test_third_attempt(self):
        config = RetryConfig(base_delay=1.0, multiplier=2.0)
        assert compute_backoff_delay(2, config) == 4.0

    def test_max_delay_caps_result(self):
        config = RetryConfig(base_delay=1.0, multiplier=2.0, max_delay=3.0)
        # Attempt 2 would be 4.0, but capped at 3.0
        assert compute_backoff_delay(2, config) == 3.0

    def test_max_delay_none_no_cap(self):
        config = RetryConfig(base_delay=1.0, multiplier=2.0, max_delay=None)
        # Attempt 10 = 1024.0, no cap
        assert compute_backoff_delay(10, config) == 1024.0

    def test_custom_base_and_multiplier(self):
        config = RetryConfig(base_delay=0.5, multiplier=3.0)
        # Attempt 0: 0.5 * 3^0 = 0.5
        assert compute_backoff_delay(0, config) == 0.5
        # Attempt 1: 0.5 * 3^1 = 1.5
        assert compute_backoff_delay(1, config) == 1.5
        # Attempt 2: 0.5 * 3^2 = 4.5
        assert compute_backoff_delay(2, config) == 4.5


class TestRetrySync:
    """Tests for retry_sync function."""

    def test_success_on_first_call(self):
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = retry_sync(func, RetryConfig(max_retries=3, base_delay=0.01))
        assert result == "success"
        assert call_count == 1

    def test_success_after_failures(self):
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient failure")
            return "recovered"

        result = retry_sync(func, RetryConfig(max_retries=3, base_delay=0.01))
        assert result == "recovered"
        assert call_count == 3

    def test_all_retries_exhausted(self):
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"failure {call_count}")

        with pytest.raises(ValueError, match="failure 4"):
            retry_sync(func, RetryConfig(max_retries=3, base_delay=0.01))
        # 1 initial + 3 retries = 4 total attempts
        assert call_count == 4

    def test_uses_default_config_when_none(self):
        """retry_sync uses default RetryConfig when config is None."""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fail once")
            return "ok"

        with patch("speechless.utils.retry.time.sleep"):
            result = retry_sync(func, None)
        assert result == "ok"

    def test_delays_between_retries(self):
        """Verify that sleep is called with correct backoff delays."""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("fail")
            return "done"

        config = RetryConfig(max_retries=3, base_delay=0.1, multiplier=2.0)
        with patch("speechless.utils.retry.time.sleep") as mock_sleep:
            result = retry_sync(func, config)

        assert result == "done"
        # Two failures → two sleeps: 0.1, 0.2
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(0.1)
        mock_sleep.assert_any_call(0.2)

    def test_preserves_exception_type(self):
        """The original exception type is preserved when retries are exhausted."""

        def func():
            raise ConnectionError("network down")

        with pytest.raises(ConnectionError, match="network down"):
            retry_sync(func, RetryConfig(max_retries=1, base_delay=0.01))
