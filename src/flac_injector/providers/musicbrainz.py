"""MusicBrainz & AcoustID provider for audio fingerprint and MBID resolution."""

from typing import Any

from flac_injector.models import TrackMetadata
from flac_injector.providers.base import BaseMetadataProvider

ACOUSTID_PUBLIC_KEY = "8XaBELgH"  # Standard open-source client key for AcoustID API


class MusicBrainzProvider(BaseMetadataProvider):
    """Resolves track metadata via AcoustID API and MusicBrainz Web Service 2."""

    name: str = "musicbrainz"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # MusicBrainz guidelines mandate a 1.0s rate limit between requests
        self.rate_limit_delay = max(1.0, self.rate_limit_delay)

    async def lookup_by_fingerprint(
        self,
        fingerprint: str,
        duration: float,
    ) -> list[TrackMetadata]:
        """Query AcoustID lookup API with Chromaprint fingerprint and duration."""
        api_key = self.settings.acoustid_api_key or ACOUSTID_PUBLIC_KEY
        params = {
            "client": api_key,
            "meta": "recordings releasegroups releases tracks usermeta",
            "duration": int(duration),
            "fingerprint": fingerprint,
        }

        try:
            resp = await self.request(
                "POST",
                "https://api.acoustid.org/v2/lookup",
                data=params,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            if data.get("status") != "ok":
                return []

            results: list[TrackMetadata] = []
            for result in data.get("results", []):
                score = float(result.get("score", 0.0))
                acoustid_id = result.get("id")

                for recording in result.get("recordings", []):
                    mbid = recording.get("id")
                    title = recording.get("title", "")
                    artists = recording.get("artists", [])
                    artist_name = (
                        ", ".join([a.get("name", "") for a in artists if a.get("name")])
                        or "Unknown Artist"
                    )
                    artist_id = artists[0].get("id") if artists else None

                    releases = recording.get("releases", [])
                    if releases:
                        for rel in releases:
                            album_name = rel.get("title", "Unknown Album")
                            album_id = rel.get("id")
                            date = rel.get("date")
                            track_num = None
                            track_total = None

                            mediums = rel.get("mediums", [])
                            if mediums:
                                tracks = mediums[0].get("tracks", [])
                                if tracks:
                                    track_num = str(tracks[0].get("position", "1"))
                                track_total = str(mediums[0].get("track_count", ""))

                            # Cover art URL from Cover Art Archive
                            cover_url = (
                                f"https://coverartarchive.org/release/{album_id}/front-500"
                                if album_id
                                else None
                            )

                            meta = TrackMetadata(
                                title=title or "Unknown Title",
                                artist=artist_name,
                                album=album_name,
                                track_number=track_num,
                                track_total=track_total,
                                date=date,
                                acoustid_id=acoustid_id,
                                musicbrainz_trackid=mbid,
                                musicbrainz_albumid=album_id,
                                musicbrainz_artistid=artist_id,
                                cover_art_url=cover_url,
                                confidence_score=min(1.0, max(0.0, score)),
                                source_provider=self.name,
                            )
                            results.append(meta)
                    else:
                        meta = TrackMetadata(
                            title=title or "Unknown Title",
                            artist=artist_name,
                            album="Unknown Album",
                            acoustid_id=acoustid_id,
                            musicbrainz_trackid=mbid,
                            musicbrainz_artistid=artist_id,
                            confidence_score=min(1.0, max(0.0, score)),
                            source_provider=self.name,
                        )
                        results.append(meta)

            return results
        except Exception:
            return []

    async def lookup_by_isrc(self, isrc: str) -> list[TrackMetadata]:
        """Query MusicBrainz Web Service for recordings with matching ISRC."""
        url = f"https://musicbrainz.org/ws/2/isrc/{isrc}?inc=artist-credits+releases&fmt=json"
        try:
            resp = await self.request("GET", url)
            if resp.status_code != 200:
                return []
            data = resp.json()

            results: list[TrackMetadata] = []
            for recording in data.get("recordings", []):
                mbid = recording.get("id")
                title = recording.get("title", "")
                artists = recording.get("artist-credit", [])
                artist_name = (
                    "".join(
                        [
                            a.get("name", "") + a.get("joinphrase", "")
                            if isinstance(a, dict)
                            else str(a)
                            for a in artists
                        ]
                    )
                    or "Unknown Artist"
                )

                releases = recording.get("releases", [])
                album_name = (
                    releases[0].get("title", "Unknown Album")
                    if releases
                    else "Unknown Album"
                )
                album_id = releases[0].get("id") if releases else None
                date = releases[0].get("date") if releases else None

                results.append(
                    TrackMetadata(
                        title=title,
                        artist=artist_name,
                        album=album_name,
                        date=date,
                        isrc=isrc,
                        musicbrainz_trackid=mbid,
                        musicbrainz_albumid=album_id,
                        confidence_score=0.95,
                        source_provider=self.name,
                    )
                )
            return results
        except Exception:
            return []

    async def lookup_by_query(
        self,
        title: str,
        artist: str | None = None,
        album: str | None = None,
    ) -> list[TrackMetadata]:
        """Search MusicBrainz recordings by textual query."""
        query_parts = [f'recording:"{title}"']
        if artist:
            query_parts.append(f'artist:"{artist}"')
        if album:
            query_parts.append(f'release:"{album}"')

        query = " AND ".join(query_parts)
        url = f"https://musicbrainz.org/ws/2/recording?query={query}&fmt=json&limit=5"

        try:
            resp = await self.request("GET", url)
            if resp.status_code != 200:
                return []
            data = resp.json()

            results: list[TrackMetadata] = []
            for rec in data.get("recordings", []):
                score = float(rec.get("score", 50)) / 100.0
                rec_title = rec.get("title", "")
                credits = rec.get("artist-credit", [])
                artist_name = (
                    "".join(
                        [
                            c.get("name", "") + c.get("joinphrase", "")
                            if isinstance(c, dict)
                            else str(c)
                            for c in credits
                        ]
                    )
                    or "Unknown Artist"
                )

                releases = rec.get("releases", [])
                album_name = (
                    releases[0].get("title", "Unknown Album")
                    if releases
                    else "Unknown Album"
                )
                album_id = releases[0].get("id") if releases else None
                date = releases[0].get("date") if releases else None

                results.append(
                    TrackMetadata(
                        title=rec_title,
                        artist=artist_name,
                        album=album_name,
                        date=date,
                        musicbrainz_trackid=rec.get("id"),
                        musicbrainz_albumid=album_id,
                        confidence_score=score,
                        source_provider=self.name,
                    )
                )
            return results
        except Exception:
            return []
