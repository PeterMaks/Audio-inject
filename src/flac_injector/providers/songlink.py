"""Songlink / Odesli metadata provider for streaming links and track resolution."""

import re
import urllib.parse
from typing import Any

from flac_injector.models import TrackMetadata
from flac_injector.providers.base import BaseMetadataProvider


class SonglinkProvider(BaseMetadataProvider):
    """Songlink (Odesli) provider resolving tracks across streaming services."""

    name: str = "songlink"
    PRIMARY_API_URL: str = "https://api.song.link/v1-alpha.1/links"
    FALLBACK_API_URL: str = "https://api.odesli.co/v1-alpha.1/links"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.rate_limit_delay = 0.5

    def _get_request_params(self, url: str) -> dict[str, str]:
        """Construct query parameters including optional user API key."""
        params: dict[str, str] = {"url": url}
        if self.settings.songlink_api_key:
            params["key"] = self.settings.songlink_api_key
        return params

    def _get_request_headers(self) -> dict[str, str]:
        """Construct authentication and polite request headers."""
        headers: dict[str, str] = {}
        if self.settings.songlink_api_key:
            key = self.settings.songlink_api_key.strip()
            headers["X-Api-Key"] = key
            headers["Authorization"] = f"Bearer {key}"
        return headers

    async def lookup_by_url(self, url: str) -> list[TrackMetadata]:
        """Resolve metadata by streaming platform or Songlink/Odesli URL."""
        clean_url = url.strip()
        if not clean_url:
            return []

        if not clean_url.startswith(("http://", "https://")):
            clean_url = f"https://{clean_url}"

        params = self._get_request_params(clean_url)
        headers = self._get_request_headers()

        # Try primary endpoint, fallback to alternate domain on network/connection failure
        payload: dict[str, Any] | None = None
        for endpoint in (self.PRIMARY_API_URL, self.FALLBACK_API_URL):
            try:
                resp = await self.request("GET", endpoint, params=params, headers=headers)
                if resp.status_code == 200:
                    payload = resp.json()
                    break
            except Exception:
                continue

        if not payload or not isinstance(payload, dict):
            return []

        return self._parse_payload(payload)

    async def lookup_by_query(
        self,
        title: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TrackMetadata]:
        """Resolve metadata by query, delegating to URL resolution if a link is detected."""
        q_strip = title.strip()
        if q_strip.startswith(("http://", "https://", "song.link", "odesli.co")):
            return await self.lookup_by_url(q_strip)

        # Step A: Discover streaming URL via Deezer public search
        query = f'"{title}"'
        if artist:
            query += f' "{artist}"'
        deezer_url = f"https://api.deezer.com/search?q={urllib.parse.quote(query)}&limit=1"
        try:
            resp = await self.request("GET", deezer_url)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                if items and items[0].get("link"):
                    results = await self.lookup_by_url(items[0]["link"])
                    if results:
                        return results
        except Exception:
            pass

        # Step B: Discover streaming URL via iTunes public search fallback
        term = f"{title} {artist or ''}".strip()
        itunes_url = (
            f"https://itunes.apple.com/search?term={urllib.parse.quote(term)}&entity=song&limit=1"
        )
        try:
            resp = await self.request("GET", itunes_url)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results and results[0].get("trackViewUrl"):
                    return await self.lookup_by_url(results[0]["trackViewUrl"])
        except Exception:
            pass

        return []

    async def lookup_by_isrc(self, isrc: str) -> list[TrackMetadata]:
        """Resolve metadata by ISRC by locating platform link and querying Songlink."""
        # Query Deezer by ISRC to get streaming track link
        url = f"https://api.deezer.com/track/isrc:{isrc.strip()}"
        try:
            resp = await self.request("GET", url)
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("error") and data.get("link"):
                    results = await self.lookup_by_url(data["link"])
                    if results:
                        return results
        except Exception:
            pass

        # Query iTunes by ISRC fallback
        itunes_url = (
            f"https://itunes.apple.com/search?term={urllib.parse.quote(isrc.strip())}"
            f"&media=music&entity=song&limit=1"
        )
        try:
            resp = await self.request("GET", itunes_url)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results and results[0].get("trackViewUrl"):
                    return await self.lookup_by_url(results[0]["trackViewUrl"])
        except Exception:
            pass

        return []

    async def lookup_by_fingerprint(
        self,
        fingerprint: str,
        duration: float,
    ) -> list[TrackMetadata]:
        """Fingerprinting is not supported by Songlink; returns empty list."""
        return []

    def _parse_payload(self, data: dict[str, Any]) -> list[TrackMetadata]:
        """Parse Odesli/Songlink JSON response into canonical TrackMetadata."""
        entity_unique_id = data.get("entityUniqueId")
        entities: dict[str, Any] = data.get("entitiesByUniqueId", {})
        links_by_platform: dict[str, Any] = data.get("linksByPlatform", {})
        page_url: str | None = data.get("pageUrl")

        if not entities:
            return []

        # Find primary entity
        primary_entity = entities.get(entity_unique_id) if entity_unique_id else None
        if not primary_entity or not primary_entity.get("title"):
            for ent in entities.values():
                if isinstance(ent, dict) and ent.get("title") and ent.get("artistName"):
                    primary_entity = ent
                    break

        if not primary_entity:
            return []

        title = str(primary_entity.get("title") or "").strip()
        artist = str(primary_entity.get("artistName") or "Unknown Artist").strip()
        if not title:
            return []

        # Check for album name across entities
        album = "Unknown Album"
        for ent in entities.values():
            if isinstance(ent, dict):
                cand_album = (
                    ent.get("albumName") or ent.get("albumTitle") or ent.get("collectionName")
                )
                if cand_album and str(cand_album).strip().lower() not in (
                    "unknown",
                    "unknown album",
                    "untitled",
                    "",
                ):
                    album = str(cand_album).strip()
                    break

        # Select highest quality artwork candidate
        best_art_url: str | None = None
        best_width: int | None = None
        best_height: int | None = None
        best_pixel_count = 0

        for ent in entities.values():
            if not isinstance(ent, dict):
                continue
            thumb = ent.get("thumbnailUrl")
            if not thumb:
                continue

            # If iTunes / Apple Music image URL, upgrade to maximum resolution (3000x3000)
            if "mzstatic.com" in thumb or "apple.com" in thumb:
                upgraded = re.sub(r"/\d+x\d+bb\.", "/3000x3000bb.", thumb)
                best_art_url = upgraded
                best_width = 3000
                best_height = 3000
                best_pixel_count = 3000 * 3000
                break

            w = int(ent.get("thumbnailWidth") or 640)
            h = int(ent.get("thumbnailHeight") or 640)
            pixel_count = w * h
            if pixel_count > best_pixel_count:
                best_art_url = thumb
                best_width = w
                best_height = h
                best_pixel_count = pixel_count

        # Build cross-platform URL tags
        extra_tags: dict[str, str] = {}
        if page_url:
            extra_tags["SONGLINK_URL"] = page_url

        platform_tag_map = {
            "spotify": "SPOTIFY_URL",
            "appleMusic": "APPLE_MUSIC_URL",
            "deezer": "DEEZER_URL",
            "youtube": "YOUTUBE_URL",
            "youtubeMusic": "YOUTUBE_MUSIC_URL",
            "tidal": "TIDAL_URL",
            "amazonMusic": "AMAZON_MUSIC_URL",
            "soundcloud": "SOUNDCLOUD_URL",
        }

        for platform_key, tag_name in platform_tag_map.items():
            link_obj = links_by_platform.get(platform_key)
            if isinstance(link_obj, dict) and link_obj.get("url"):
                extra_tags[tag_name] = link_obj["url"]

        if "YOUTUBE_URL" not in extra_tags and "YOUTUBE_MUSIC_URL" in extra_tags:
            extra_tags["YOUTUBE_URL"] = extra_tags["YOUTUBE_MUSIC_URL"]

        # Check for ISRC identifier if available
        isrc = None
        for ent in entities.values():
            if isinstance(ent, dict) and ent.get("isrc"):
                isrc = str(ent["isrc"]).strip()
                break

        meta = TrackMetadata(
            title=title,
            artist=artist,
            album=album,
            isrc=isrc,
            cover_art_url=best_art_url,
            cover_art_width=best_width,
            cover_art_height=best_height,
            source_provider=self.name,
            confidence_score=0.92,
            extra_tags=extra_tags,
        )

        return [meta]
