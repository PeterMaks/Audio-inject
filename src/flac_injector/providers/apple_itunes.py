"""Apple iTunes Search API provider with 3000x3000 ultra high-resolution cover art."""

import re
from typing import Any

from flac_injector.models import TrackMetadata
from flac_injector.providers.base import BaseMetadataProvider


class AppleITunesProvider(BaseMetadataProvider):
    """Zero-authentication iTunes Search API provider for rich tags and 3000x3000 art."""

    name: str = "apple_itunes"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.rate_limit_delay = 0.3  # Polite rate limit for iTunes API

    def _upgrade_cover_art_url(self, raw_url: str | None, resolution: int = 3000) -> str | None:
        """Upgrade iTunes thumbnail artwork URL to maximum resolution (up to 3000x3000)."""
        if not raw_url:
            return None
        # Replace /100x100bb.jpg or /60x60bb.jpg with /{resolution}x{resolution}bb.jpg
        return re.sub(r"/\d+x\d+bb\.", f"/{resolution}x{resolution}bb.", raw_url)

    async def lookup_by_fingerprint(
        self,
        fingerprint: str,
        duration: float,
    ) -> list[TrackMetadata]:
        """AcoustID is not natively supported by iTunes; returns empty list."""
        return []

    async def lookup_by_isrc(self, isrc: str) -> list[TrackMetadata]:
        """Search iTunes for songs matching ISRC."""
        url = f"https://itunes.apple.com/search?term={isrc}&media=music&entity=song&limit=5"
        try:
            resp = await self.request("GET", url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            return self._parse_results(data.get("results", []))
        except Exception:
            return []

    async def lookup_by_query(
        self,
        title: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TrackMetadata]:
        """Search iTunes song catalog by title and artist."""
        search_terms = [title]
        if artist:
            search_terms.append(artist)
        if album:
            search_terms.append(album)

        term = " ".join(search_terms)
        params = {
            "term": term,
            "media": "music",
            "entity": "song",
            "limit": 5,
        }

        try:
            resp = await self.request(
                "GET",
                "https://itunes.apple.com/search",
                params=params,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return self._parse_results(data.get("results", []))
        except Exception:
            return []

    def _parse_results(self, items: list[dict[str, Any]]) -> list[TrackMetadata]:
        """Convert iTunes JSON search results into canonical TrackMetadata."""
        results: list[TrackMetadata] = []
        for item in items:
            raw_title = item.get("trackName")
            raw_artist = item.get("artistName")
            raw_album = item.get("collectionName")

            if not raw_title or not raw_artist:
                continue

            raw_date = item.get("releaseDate")
            date_str = raw_date[:10] if raw_date and len(raw_date) >= 10 else None

            # High-res cover art transformation
            raw_art = item.get("artworkUrl100")
            high_res_art = self._upgrade_cover_art_url(raw_art, resolution=3000)

            genre = [item.get("primaryGenreName")] if item.get("primaryGenreName") else []
            explicit = item.get("trackExplicitness") == "explicit"

            track_num = str(item.get("trackNumber")) if item.get("trackNumber") else None
            track_total = str(item.get("trackCount")) if item.get("trackCount") else None
            disc_num = str(item.get("discNumber")) if item.get("discNumber") else None
            disc_total = str(item.get("discCount")) if item.get("discCount") else None

            meta = TrackMetadata(
                title=raw_title,
                artist=raw_artist,
                album=raw_album or "Unknown Album",
                track_number=track_num,
                track_total=track_total,
                disc_number=disc_num,
                disc_total=disc_total,
                date=date_str,
                genre=genre,
                explicit=explicit,
                cover_art_url=high_res_art,
                cover_art_width=3000,
                cover_art_height=3000,
                source_provider=self.name,
                confidence_score=0.85,
            )
            results.append(meta)
        return results
