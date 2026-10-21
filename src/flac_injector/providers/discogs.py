"""Discogs Database API provider for exhaustive physical releases, styles, and credits."""

import re
from typing import Any

from rapidfuzz import fuzz

from flac_injector.models import TrackMetadata
from flac_injector.providers.base import BaseMetadataProvider


class DiscogsProvider(BaseMetadataProvider):
    """Discogs API provider for rich release metadata, styles, and vinyl/CD catalog info."""

    name: str = "discogs"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.rate_limit_delay = max(1.0, self.rate_limit_delay)

    @staticmethod
    def _sanitize_discogs_name(name: str | None) -> str:
        """Strip Discogs numeric disambiguation suffixes like 'Artist (2)'."""
        if not name:
            return ""
        return re.sub(r"\s*\(\d+\)$", "", name).strip()

    def _get_auth_headers(self) -> dict[str, str]:
        """Build request headers with Discogs token authentication."""
        headers: dict[str, str] = {
            "User-Agent": self.settings.musicbrainz_user_agent,
            "Accept": "application/json",
        }
        if self.settings.discogs_token:
            headers["Authorization"] = f"Discogs token={self.settings.discogs_token.strip()}"
        return headers

    async def fetch_cover_art(self, url: str) -> tuple[bytes, str] | None:
        """Download cover art image bytes, passing Discogs token if applicable."""
        try:
            headers = self._get_auth_headers()
            resp = await self.request("GET", url, headers=headers)
            if resp.status_code == 200:
                mime = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                return resp.content, mime
        except Exception:
            pass
        return None

    async def lookup_by_fingerprint(
        self,
        fingerprint: str,
        duration: float,
    ) -> list[TrackMetadata]:
        """Acoustic fingerprinting is not supported by Discogs; returns empty list."""
        return []

    async def lookup_by_isrc(self, isrc: str) -> list[TrackMetadata]:
        """Search Discogs database for releases matching an ISRC identifier."""
        if not self.settings.discogs_token:
            return []

        url = "https://api.discogs.com/database/search"
        params = {
            "type": "release",
            "q": isrc,
            "per_page": 5,
        }
        try:
            resp = await self.request("GET", url, params=params, headers=self._get_auth_headers())
            if resp.status_code != 200:
                return []
            data = resp.json()
            items = data.get("results", [])
            results: list[TrackMetadata] = []
            for item in items[:2]:
                release_id = item.get("id")
                detail = await self._fetch_release_detail(release_id) if release_id else None
                meta = self._parse_release_detail(detail, query_title="", query_artist=None) if detail else None
                if not meta:
                    meta = self._parse_search_item(item, query_title="", query_artist=None)
                if meta:
                    meta.isrc = isrc
                    results.append(meta)
            return results
        except Exception:
            return []

    async def lookup_by_query(
        self,
        title: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TrackMetadata]:
        """Search Discogs release database by track title, artist, and optional album."""
        if not self.settings.discogs_token:
            return []

        url = "https://api.discogs.com/database/search"
        params: dict[str, Any] = {
            "type": "release",
            "track": title,
            "per_page": 5,
        }
        if artist:
            params["artist"] = artist
        if album:
            params["release_title"] = album

        try:
            resp = await self.request("GET", url, params=params, headers=self._get_auth_headers())
            if resp.status_code != 200:
                return []
            data = resp.json()
            items = data.get("results", [])

            results: list[TrackMetadata] = []
            for item in items[:3]:
                release_id = item.get("id")
                detail = await self._fetch_release_detail(release_id) if release_id else None
                if detail:
                    meta = self._parse_release_detail(detail, query_title=title, query_artist=artist)
                    if meta:
                        results.append(meta)
                        continue

                # Fallback to search item summary
                meta = self._parse_search_item(item, query_title=title, query_artist=artist)
                if meta:
                    results.append(meta)

            return results
        except Exception:
            return []

    async def _fetch_release_detail(self, release_id: int | str) -> dict[str, Any] | None:
        """Fetch full release details including complete tracklist, credits, and images."""
        url = f"https://api.discogs.com/releases/{release_id}"
        try:
            resp = await self.request("GET", url, headers=self._get_auth_headers())
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _parse_release_detail(
        self,
        detail: dict[str, Any],
        query_title: str,
        query_artist: str | None = None,
    ) -> TrackMetadata | None:
        """Parse Discogs release detail JSON into canonical TrackMetadata."""
        album_name = detail.get("title", "Unknown Album")
        release_id = str(detail.get("id", ""))

        # Resolve release artist
        release_artists = detail.get("artists", [])
        primary_artist = (
            self._sanitize_discogs_name(release_artists[0].get("name"))
            if release_artists and isinstance(release_artists[0], dict)
            else (query_artist or "Unknown Artist")
        )

        tracklist = detail.get("tracklist", [])
        matched_track: dict[str, Any] | None = None
        best_ratio = 0.0

        for t in tracklist:
            if not isinstance(t, dict):
                continue
            if t.get("type_") == "heading":
                continue
            t_title = t.get("title", "")
            if not t_title:
                continue

            if query_title:
                ratio = fuzz.token_sort_ratio(t_title.lower(), query_title.lower())
                if ratio > best_ratio:
                    best_ratio = ratio
                    matched_track = t
            elif not matched_track:
                matched_track = t

        # Track metadata
        track_title = matched_track.get("title") if matched_track else (query_title or album_name)
        track_pos = str(matched_track.get("position", "")) if matched_track and matched_track.get("position") else None

        # Track artist if specified individually
        track_artist = primary_artist
        if matched_track and matched_track.get("artists"):
            t_artists = matched_track["artists"]
            if isinstance(t_artists, list) and t_artists and isinstance(t_artists[0], dict):
                track_artist = self._sanitize_discogs_name(t_artists[0].get("name")) or primary_artist

        # Composer / Writer from extraartists
        composer: str | None = None
        composers_list: list[str] = []
        extra_artists = []
        if matched_track and matched_track.get("extraartists"):
            extra_artists.extend(matched_track["extraartists"])
        if detail.get("extraartists"):
            extra_artists.extend(detail["extraartists"])

        for ea in extra_artists:
            if isinstance(ea, dict):
                role = ea.get("role", "").lower()
                if any(w in role for w in ("written-by", "written by", "composer", "music by", "words by")):
                    clean_ea = self._sanitize_discogs_name(ea.get("name"))
                    if clean_ea and clean_ea not in composers_list:
                        composers_list.append(clean_ea)
        if composers_list:
            composer = ", ".join(composers_list)

        # Date & Year
        date_str = str(detail.get("released") or detail.get("year") or "").strip()
        year_str = str(detail.get("year", "")) if detail.get("year") else (date_str[:4] if len(date_str) >= 4 and date_str[:4].isdigit() else None)

        # Genres and Styles combined
        genres: list[str] = []
        for g in detail.get("genres", []):
            if g and g not in genres:
                genres.append(g)
        for s in detail.get("styles", []):
            if s and s not in genres:
                genres.append(s)

        # Labels & Barcode
        label: str | None = None
        labels = detail.get("labels", [])
        if labels and isinstance(labels[0], dict):
            label = labels[0].get("name")

        barcode: str | None = None
        isrc: str | None = None
        for ident in detail.get("identifiers", []):
            if isinstance(ident, dict):
                i_type = ident.get("type", "").lower()
                val = ident.get("value", "").strip()
                if "barcode" in i_type and not barcode:
                    barcode = val
                elif "isrc" in i_type and not isrc:
                    isrc = val

        # Cover Art
        cover_url: str | None = None
        cover_w: int | None = None
        cover_h: int | None = None
        images = detail.get("images", [])
        if images and isinstance(images, list):
            primary_imgs = [img for img in images if isinstance(img, dict) and img.get("type") == "primary"]
            chosen = primary_imgs[0] if primary_imgs else images[0]
            if isinstance(chosen, dict):
                cover_url = chosen.get("uri") or chosen.get("resource_url")
                cover_w = chosen.get("width")
                cover_h = chosen.get("height")

        track_count = len([t for t in tracklist if isinstance(t, dict) and t.get("position")])
        track_total = str(track_count) if track_count > 0 else None

        confidence = 0.88 if (matched_track and best_ratio >= 75) else 0.75

        return TrackMetadata(
            title=track_title,
            artist=track_artist,
            album=album_name,
            album_artist=primary_artist,
            track_number=track_pos,
            track_total=track_total,
            date=date_str or None,
            year=year_str or None,
            genre=genres,
            isrc=isrc,
            barcode=barcode,
            label=label,
            composer=composer,
            cover_art_url=cover_url,
            cover_art_width=cover_w,
            cover_art_height=cover_h,
            source_provider=self.name,
            confidence_score=confidence,
            extra_tags={"DISCOGS_RELEASE_ID": release_id} if release_id else {},
        )

    def _parse_search_item(
        self,
        item: dict[str, Any],
        query_title: str,
        query_artist: str | None = None,
    ) -> TrackMetadata | None:
        """Parse Discogs search item summary into TrackMetadata."""
        item_title = item.get("title", "")
        if " - " in item_title:
            artist_part, album_part = item_title.split(" - ", 1)
        else:
            artist_part = query_artist or "Unknown Artist"
            album_part = item_title or "Unknown Album"

        artist = self._sanitize_discogs_name(artist_part)
        album = album_part.strip()
        release_id = str(item.get("id", ""))

        genres: list[str] = []
        for g in item.get("genre", []):
            if g and g not in genres:
                genres.append(g)
        for s in item.get("style", []):
            if s and s not in genres:
                genres.append(s)

        cover_url = item.get("cover_image") or item.get("thumb")
        labels = item.get("label", [])
        label = labels[0] if labels and isinstance(labels[0], str) else None

        barcodes = item.get("barcode", [])
        barcode = barcodes[0] if barcodes and isinstance(barcodes[0], str) else None

        year = str(item.get("year", "")) if item.get("year") else None

        return TrackMetadata(
            title=query_title or album,
            artist=artist,
            album=album,
            date=year,
            year=year,
            genre=genres,
            barcode=barcode,
            label=label,
            cover_art_url=cover_url,
            source_provider=self.name,
            confidence_score=0.72,
            extra_tags={"DISCOGS_RELEASE_ID": release_id} if release_id else {},
        )
