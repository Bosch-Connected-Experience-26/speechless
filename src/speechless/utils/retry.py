"""Exponential backoff retry utility for resilient operations."""

from dataclasses import dataclass
from typing import Callable, Optional, TypeVar
import time

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior with exponential backoff.

    Attributes:
        max_retries: Maximum number of retry attempts (default 3).
        base_delay: Initial delay in seconds before first retry (default 1.0).
        multiplier: Factor by which delay increases each retry (default 2.0).
        max_delay: Optional cap on delay in seconds. None means no cap.
    """

    max_retries: int = 3
    base_delay: float = 1.0
    multiplier: float = 2.0
    max_delay: Optional[float] = None


def compute_backoff_delay(attempt: int, config: RetryConfig) -> float:
    """Compute the backoff delay for a given retry attempt.

    Args:
        attempt: Zero-based attempt index (0 = first retry, 1 = second retry, etc.).
        config: Retry configuration with base_delay, multiplier, and optional max_delay.

    Returns:
        The delay in seconds before the next retry, capped at max_delay if set.
    """
    delay = config.base_delay * (config.multiplier ** attempt)
    if config.max_delay is not None:
        delay = min(delay, config.max_delay)
    return delay


def retry_sync(func: Callable[[], T], config: Optional[RetryConfig] = None) -> T:
    """Execute a function with synchronous retry and exponential backoff.

    Calls func(). If it raises an exception, retries up to config.max_retries times
    with exponential backoff delays between attempts.

    Args:
        func: A callable that takes no arguments and returns a value.
        config: Retry configuration. Uses defaults if None.

    Returns:
        The return value of func() on success.

    Raises:
        The last exception raised by func() if all retries are exhausted.
    """
    if config is None:
        config = RetryConfig()

    last_exception: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exception = exc
            if attempt < config.max_retries:
                delay = compute_backoff_delay(attempt, config)
                time.sleep(delay)

    # This should never be reached without last_exception being set,
    # but satisfy the type checker.
    assert last_exception is not None
    raise last_exception
