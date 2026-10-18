"""Deezer Public API provider for ISRC, BPM, explicit rating, and cover art."""

from typing import Any

from flac_injector.models import TrackMetadata
from flac_injector.providers.base import BaseMetadataProvider


class DeezerProvider(BaseMetadataProvider):
    """Zero-authentication Deezer API provider for musical attributes (BPM, explicit)."""

    name: str = "deezer"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.rate_limit_delay = 0.25  # Polite rate limit for Deezer API

    async def lookup_by_fingerprint(
        self,
        fingerprint: str,
        duration: float,
    ) -> list[TrackMetadata]:
        """AcoustID is not supported directly by Deezer; returns empty list."""
        return []

    async def lookup_by_isrc(self, isrc: str) -> list[TrackMetadata]:
        """Look up track by exact ISRC identifier on Deezer."""
        url = f"https://api.deezer.com/track/isrc:{isrc}"
        try:
            resp = await self.request("GET", url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if "error" in data or not data.get("id"):
                return []
            meta = self._parse_track_detail(data)
            return [meta] if meta else []
        except Exception:
            return []

    async def lookup_by_query(
        self,
        title: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TrackMetadata]:
        """Search Deezer catalog by track title and artist name."""
        query_parts = [f'track:"{title}"']
        if artist:
            query_parts.append(f'artist:"{artist}"')
        if album:
            query_parts.append(f'album:"{album}"')

        q = " ".join(query_parts)
        url = f"https://api.deezer.com/search?q={q}&limit=5"

        try:
            resp = await self.request("GET", url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            items = data.get("data", [])

            results: list[TrackMetadata] = []
            for item in items:
                track_id = item.get("id")
                # Attempt to fetch full track details for BPM and complete info
                track_data = await self._fetch_track_detail(track_id) if track_id else item
                meta = self._parse_track_detail(track_data or item)
                if meta:
                    results.append(meta)
            return results
        except Exception:
            return []

    async def _fetch_track_detail(self, track_id: int | str) -> dict[str, Any] | None:
        """Fetch rich track details including BPM and uncompressed metadata."""
        url = f"https://api.deezer.com/track/{track_id}"
        try:
            resp = await self.request("GET", url)
            if resp.status_code == 200:
                data = resp.json()
                if "error" not in data:
                    return data
        except Exception:
            pass
        return None

    def _parse_track_detail(self, data: dict[str, Any]) -> TrackMetadata | None:
        """Transform Deezer track JSON payload into canonical TrackMetadata."""
        title = data.get("title")
        artist_obj = data.get("artist", {})
        artist = artist_obj.get("name") if isinstance(artist_obj, dict) else None

        if not title or not artist:
            return None

        album_obj = data.get("album", {})
        album_name = (
            album_obj.get("title", "Unknown Album")
            if isinstance(album_obj, dict)
            else "Unknown Album"
        )
        cover_url = (
            album_obj.get("cover_xl") or album_obj.get("cover_big")
            if isinstance(album_obj, dict)
            else None
        )

        track_pos = str(data.get("track_position", "1")) if data.get("track_position") else None
        release_date = data.get("release_date")
        bpm = float(data["bpm"]) if data.get("bpm") else None
        explicit = bool(data.get("explicit_lyrics", False))
        isrc = data.get("isrc")

        return TrackMetadata(
            title=title,
            artist=artist,
            album=album_name,
            track_number=track_pos,
            date=release_date,
            isrc=isrc,
            bpm=bpm,
            explicit=explicit,
            cover_art_url=cover_url,
            cover_art_width=1000 if cover_url else None,
            cover_art_height=1000 if cover_url else None,
            source_provider=self.name,
            confidence_score=0.85,
        )
