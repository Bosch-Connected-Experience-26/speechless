"""Exponential backoff retry utility for resilient operations."""

import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for exponential backoff retry."""

    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    multiplier: float = 2.0


def compute_backoff_delay(attempt: int, config: RetryConfig) -> float:
    """Compute the delay for a given retry attempt using exponential backoff.

    attempt is 0-indexed (0 = first retry after initial failure).
    """
    delay = config.base_delay * (config.multiplier**attempt)
    return min(delay, config.max_delay)


def retry_sync(
    func: Callable[[], T],
    config: RetryConfig = RetryConfig(),
) -> T:
    """Execute func with exponential backoff retry. Raises last exception on exhaustion."""
    last_error: Optional[Exception] = None
    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < config.max_retries:
                delay = compute_backoff_delay(attempt, config)
                time.sleep(delay)
    raise last_error  # type: ignore[misc]
