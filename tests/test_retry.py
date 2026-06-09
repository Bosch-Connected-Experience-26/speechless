"""Tests for the retry utility module."""

import time
from unittest.mock import MagicMock

import pytest

from speechless.utils.retry import RetryConfig, compute_backoff_delay, retry_sync


class TestRetryConfig:
    """Tests for RetryConfig defaults and configuration."""

    def test_default_values(self):
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.multiplier == 2.0

    def test_custom_values(self):
        config = RetryConfig(max_retries=5, base_delay=0.5, max_delay=10.0, multiplier=3.0)
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 10.0
        assert config.multiplier == 3.0


class TestComputeBackoffDelay:
    """Tests for compute_backoff_delay function."""

    def test_first_attempt(self):
        config = RetryConfig(base_delay=1.0, multiplier=2.0, max_delay=30.0)
        assert compute_backoff_delay(0, config) == 1.0

    def test_second_attempt(self):
        config = RetryConfig(base_delay=1.0, multiplier=2.0, max_delay=30.0)
        assert compute_backoff_delay(1, config) == 2.0

    def test_third_attempt(self):
        config = RetryConfig(base_delay=1.0, multiplier=2.0, max_delay=30.0)
        assert compute_backoff_delay(2, config) == 4.0

    def test_capped_at_max_delay(self):
        config = RetryConfig(base_delay=1.0, multiplier=2.0, max_delay=5.0)
        # attempt 3 -> 1.0 * 2^3 = 8.0, capped to 5.0
        assert compute_backoff_delay(3, config) == 5.0

    def test_custom_multiplier(self):
        config = RetryConfig(base_delay=0.5, multiplier=3.0, max_delay=30.0)
        # attempt 2 -> 0.5 * 3^2 = 4.5
        assert compute_backoff_delay(2, config) == 4.5


class TestRetrySync:
    """Tests for retry_sync function."""

    def test_success_on_first_attempt(self):
        func = MagicMock(return_value="ok")
        result = retry_sync(func, RetryConfig(max_retries=3))
        assert result == "ok"
        assert func.call_count == 1

    def test_success_after_failures(self):
        func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "ok"])
        config = RetryConfig(max_retries=3, base_delay=0.01)
        result = retry_sync(func, config)
        assert result == "ok"
        assert func.call_count == 3

    def test_raises_after_exhausting_retries(self):
        func = MagicMock(side_effect=ValueError("always fails"))
        config = RetryConfig(max_retries=2, base_delay=0.01)
        with pytest.raises(ValueError, match="always fails"):
            retry_sync(func, config)
        # Initial attempt + 2 retries = 3 calls
        assert func.call_count == 3

    def test_delay_between_retries(self):
        func = MagicMock(side_effect=[ValueError("fail"), "ok"])
        config = RetryConfig(max_retries=1, base_delay=0.1, multiplier=2.0)
        start = time.monotonic()
        retry_sync(func, config)
        elapsed = time.monotonic() - start
        # Should have waited at least base_delay (0.1s) between attempts
        assert elapsed >= 0.09

    def test_no_delay_on_success(self):
        func = MagicMock(return_value="ok")
        config = RetryConfig(max_retries=3, base_delay=1.0)
        start = time.monotonic()
        retry_sync(func, config)
        elapsed = time.monotonic() - start
        # Should complete almost instantly
        assert elapsed < 0.1
