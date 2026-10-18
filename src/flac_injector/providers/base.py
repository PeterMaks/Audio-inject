"""Base asynchronous metadata provider with rate-limiting and connection management."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from flac_injector.config import Settings, get_settings
from flac_injector.models import TrackMetadata


class BaseMetadataProvider(ABC):
    """Abstract base provider handling rate-limiting and HTTP requests."""

    name: str = "base"

    def __init__(
        self,
        settings: Settings | None = None,
        rate_limit_delay: float | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.rate_limit_delay = (
            rate_limit_delay
            if rate_limit_delay is not None
            else self.settings.rate_limit_delay
        )
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "User-Agent": self.settings.musicbrainz_user_agent,
                "Accept": "application/json",
            }
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=self.settings.request_timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _throttle(self) -> None:
        """Ensure polite rate-limiting between successive API calls."""
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - elapsed)
            self._last_request_time = time.monotonic()

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute a rate-limited HTTP request."""
        await self._throttle()
        client = await self.get_client()
        response = await client.request(method, url, **kwargs)
        return response

    async def fetch_cover_art(self, url: str) -> tuple[bytes, str] | None:
        """Download cover art image bytes and determine MIME type."""
        try:
            resp = await self.request("GET", url)
            if resp.status_code == 200:
                mime = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                return resp.content, mime
        except Exception:
            pass
        return None

    @abstractmethod
    async def lookup_by_fingerprint(
        self,
        fingerprint: str,
        duration: float,
    ) -> list[TrackMetadata]:
        """Resolve metadata using an acoustic fingerprint."""
        return []

    @abstractmethod
    async def lookup_by_isrc(self, isrc: str) -> list[TrackMetadata]:
        """Resolve metadata using an ISRC code."""
        return []

    @abstractmethod
    async def lookup_by_query(
        self,
        title: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TrackMetadata]:
        """Resolve metadata using textual search query."""
        return []
