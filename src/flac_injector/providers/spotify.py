"""Spotify Web API provider using Client Credentials flow."""

import base64
import time
from typing import Any

from flac_injector.models import TrackMetadata
from flac_injector.providers.base import BaseMetadataProvider


class SpotifyProvider(BaseMetadataProvider):
    """Spotify Web API provider for canonical streaming track data."""

    name: str = "spotify"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.rate_limit_delay = 0.2
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def _ensure_token(self) -> str | None:
        """Authenticate with Spotify API using client_credentials flow."""
        if not self.settings.spotify_client_id or not self.settings.spotify_client_secret:
            return None

        # Return cached token if still valid (with 60s buffer)
        if self._access_token and time.monotonic() < self._token_expires_at - 60:
            return self._access_token

        auth_header = base64.b64encode(
            f"{self.settings.spotify_client_id}:{self.settings.spotify_client_secret}".encode()
        ).decode("utf-8")

        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}

        try:
            client = await self.get_client()
            resp = await client.post(
                "https://accounts.spotify.com/api/token",
                headers=headers,
                data=data,
            )
            if resp.status_code == 200:
                payload = resp.json()
                self._access_token = payload.get("access_token")
                expires_in = float(payload.get("expires_in", 3600))
                self._token_expires_at = time.monotonic() + expires_in
                return self._access_token
        except Exception:
            pass
        return None

    async def lookup_by_fingerprint(
        self,
        fingerprint: str,
        duration: float,
    ) -> list[TrackMetadata]:
        """Acoustic fingerprinting is not supported on Spotify; returns empty."""
        return []

    async def lookup_by_isrc(self, isrc: str) -> list[TrackMetadata]:
        """Search Spotify tracks by ISRC identifier."""
        token = await self._ensure_token()
        if not token:
            return []

        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://api.spotify.com/v1/search?q=isrc:{isrc}&type=track&limit=5"

        try:
            resp = await self.request("GET", url, headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json()
            return self._parse_tracks(data.get("tracks", {}).get("items", []))
        except Exception:
            return []

    async def lookup_by_query(
        self,
        title: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TrackMetadata]:
        """Search Spotify tracks by title, artist, and album query."""
        token = await self._ensure_token()
        if not token:
            return []

        query_parts = [f"track:{title}"]
        if artist:
            query_parts.append(f"artist:{artist}")
        if album:
            query_parts.append(f"album:{album}")

        q = " ".join(query_parts)
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://api.spotify.com/v1/search?q={q}&type=track&limit=5"

        try:
            resp = await self.request("GET", url, headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json()
            return self._parse_tracks(data.get("tracks", {}).get("items", []))
        except Exception:
            return []

    def _parse_tracks(self, items: list[dict[str, Any]]) -> list[TrackMetadata]:
        """Convert Spotify track objects into canonical TrackMetadata."""
        results: list[TrackMetadata] = []
        for item in items:
            name = item.get("name")
            artists = item.get("artists", [])
            artist_name = (
                ", ".join([a.get("name", "") for a in artists if a.get("name")])
                or "Unknown Artist"
            )

            if not name:
                continue

            album_obj = item.get("album", {})
            album_name = album_obj.get("name", "Unknown Album")
            release_date = album_obj.get("release_date")
            images = album_obj.get("images", [])
            cover_url = images[0].get("url") if images else None

            isrc = item.get("external_ids", {}).get("isrc")
            track_num = str(item.get("track_number")) if item.get("track_number") else None
            track_total = (
                str(album_obj.get("total_tracks")) if album_obj.get("total_tracks") else None
            )
            disc_num = str(item.get("disc_number")) if item.get("disc_number") else None
            explicit = bool(item.get("explicit", False))

            meta = TrackMetadata(
                title=name,
                artist=artist_name,
                album=album_name,
                track_number=track_num,
                track_total=track_total,
                disc_number=disc_num,
                date=release_date,
                isrc=isrc,
                explicit=explicit,
                cover_art_url=cover_url,
                cover_art_width=640 if cover_url else None,
                cover_art_height=640 if cover_url else None,
                source_provider=self.name,
                confidence_score=0.90,
            )
            results.append(meta)
        return results
