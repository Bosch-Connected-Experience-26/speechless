"""Real-time information query support.

Extends the cloud processor to handle fuel price queries (EUR per liter),
restaurant availability, and other live data. Returns cached data when
live services are unavailable.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RealTimeQueryResult:
    """Result from a real-time data query."""

    text: str
    data_source: str  # e.g., "live", "cached"
    timestamp: str  # ISO format
    success: bool
    error_message: Optional[str] = None


@dataclass
class CachedEntry:
    """A cached real-time data entry with expiry."""

    result: RealTimeQueryResult
    expires_at: float  # monotonic time


class RealTimeQueryHandler:
    """Handles real-time information queries (fuel prices, restaurants, etc.).

    When live services are unavailable, returns cached data if available.
    All fuel prices are returned in EUR per liter.

    Args:
        cache_ttl: Cache time-to-live in seconds (default 300 = 5 minutes).
        bedrock_client: Optional BedrockClient for cloud-augmented queries.
    """

    def __init__(self, cache_ttl: float = 300.0, bedrock_client=None):
        self.cache_ttl = cache_ttl
        self.bedrock_client = bedrock_client
        self._cache: dict[str, CachedEntry] = {}

    def query_fuel_price(
        self, station_name: Optional[str] = None
    ) -> RealTimeQueryResult:
        """Query current fuel price in EUR per liter.

        Args:
            station_name: Optional specific station to query.

        Returns:
            RealTimeQueryResult with price info or cached fallback.
        """
        from datetime import datetime, timezone

        cache_key = f"fuel_price:{station_name or 'default'}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Try live query via Bedrock
        if self.bedrock_client:
            try:
                query = (
                    f"What is the current fuel price at {station_name}?"
                    if station_name
                    else "What is the current fuel price per liter in EUR?"
                )
                response = self.bedrock_client.converse(query)
                if response.success:
                    result = RealTimeQueryResult(
                        text=response.text,
                        data_source="live",
                        timestamp=now_iso,
                        success=True,
                    )
                    self._update_cache(cache_key, result)
                    return result
            except Exception:
                pass

        # Fallback to cache
        cached = self._get_cached(cache_key)
        if cached:
            return RealTimeQueryResult(
                text=cached.result.text,
                data_source="cached",
                timestamp=cached.result.timestamp,
                success=True,
            )

        # No live data, no cache
        return RealTimeQueryResult(
            text="Live fuel price data is currently unavailable.",
            data_source="unavailable",
            timestamp=now_iso,
            success=False,
            error_message="Live data services unavailable and no cached data.",
        )

    def query_restaurant_availability(
        self, cuisine: Optional[str] = None, location: Optional[str] = None
    ) -> RealTimeQueryResult:
        """Query restaurant availability and operating hours.

        Args:
            cuisine: Optional cuisine type filter.
            location: Optional location/area.

        Returns:
            RealTimeQueryResult with restaurant info or cached fallback.
        """
        from datetime import datetime, timezone

        cache_key = f"restaurant:{cuisine or 'any'}:{location or 'nearby'}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Try live query via Bedrock
        if self.bedrock_client:
            try:
                parts = ["Find restaurants"]
                if cuisine:
                    parts.append(f"serving {cuisine}")
                if location:
                    parts.append(f"near {location}")
                parts.append("that are currently open")
                query = " ".join(parts) + "."

                response = self.bedrock_client.converse(query)
                if response.success:
                    result = RealTimeQueryResult(
                        text=response.text,
                        data_source="live",
                        timestamp=now_iso,
                        success=True,
                    )
                    self._update_cache(cache_key, result)
                    return result
            except Exception:
                pass

        # Fallback to cache
        cached = self._get_cached(cache_key)
        if cached:
            return RealTimeQueryResult(
                text=cached.result.text,
                data_source="cached",
                timestamp=cached.result.timestamp,
                success=True,
            )

        # No live data, no cache
        return RealTimeQueryResult(
            text="Live restaurant data is currently unavailable.",
            data_source="unavailable",
            timestamp=now_iso,
            success=False,
            error_message="Live data services unavailable and no cached data.",
        )

    def _update_cache(self, key: str, result: RealTimeQueryResult) -> None:
        """Store a result in the cache with TTL."""
        self._cache[key] = CachedEntry(
            result=result,
            expires_at=time.monotonic() + self.cache_ttl,
        )

    def _get_cached(self, key: str) -> Optional[CachedEntry]:
        """Retrieve a non-expired cached entry."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[key]
            return None
        return entry

    def clear_cache(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
