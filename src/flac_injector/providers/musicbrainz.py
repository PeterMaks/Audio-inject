from typing import Any

from rapidfuzz import fuzz

from flac_injector.models import TrackMetadata
from flac_injector.providers.base import BaseMetadataProvider

ACOUSTID_PUBLIC_KEY = "8XaBELgH"  # Standard open-source client key for AcoustID API


def score_release(
    rel: dict[str, Any],
    recording_artist: str,
    existing_albumartist: str | None = None,
) -> int:
    """Rank releases deterministically to prevent compilation / Various Artists artwork bleeding.

    Bonuses:
      +50: Primary type is Album, status is Official, and release artist matches recording artist.
      +35: Primary type is Single or EP, Official status, and matches recording artist.
    Penalties:
      -100: Secondary types include Compilation, Soundtrack, DJ-mix, Mixtape/Street,
            OR release artist credit is 'Various Artists'
            (unless user's existing tag explicitly specifies ALBUMARTIST = Various Artists).
    """
    score = 0
    rg = rel.get("releasegroup") or rel.get("release-group") or {}
    primary_type = (
        str(rel.get("type") or rg.get("type") or rg.get("primary-type") or "").strip().lower()
    )

    status = str(rel.get("status") or rg.get("status") or "official").strip().lower()

    raw_sec = rel.get("secondarytypes") or rg.get("secondary-types") or []
    sec_types = [str(s).strip().lower() for s in raw_sec]

    rel_artists = (
        rel.get("artists")
        or rg.get("artists")
        or rel.get("artist-credit")
        or rg.get("artist-credit")
        or []
    )
    if isinstance(rel_artists, list):
        names = []
        for a in rel_artists:
            if isinstance(a, dict):
                names.append(a.get("name") or "")
            else:
                names.append(str(a))
        rel_artist_str = ", ".join(n for n in names if n)
    else:
        rel_artist_str = str(rel_artists)

    is_various_artists = (
        "various artists" in rel_artist_str.lower() or rel_artist_str.strip().lower() == "various"
    )

    compilation_penalties = {"compilation", "soundtrack", "dj-mix", "mixtape/street"}
    is_compilation = (
        any(p in sec_types or p == primary_type for p in compilation_penalties)
        or is_various_artists
    )

    user_is_various = bool(existing_albumartist and "various" in existing_albumartist.lower())

    if is_compilation and not user_is_various:
        score -= 100

    artist_matches = (
        fuzz.token_set_ratio(recording_artist.lower(), rel_artist_str.lower()) >= 80
        if (recording_artist and rel_artist_str)
        else True
    )

    if (
        primary_type == "album"
        and status == "official"
        and artist_matches
        and not is_various_artists
    ):
        score += 50
    elif (
        primary_type in ("single", "ep")
        and status == "official"
        and artist_matches
        and not is_various_artists
    ):
        score += 35

    return score


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
                    artist_list = [a.get("name", "").strip() for a in artists if a.get("name")]
                    artist_name = ", ".join(artist_list) or "Unknown Artist"
                    artist_id = artists[0].get("id") if artists else None

                    releases = recording.get("releases", [])
                    if releases:
                        scored_releases = [
                            (score_release(rel, artist_name), rel) for rel in releases
                        ]
                        scored_releases.sort(key=lambda x: x[0], reverse=True)

                        for rel_score, rel in scored_releases:
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

                            # Cover art URL - never inject compilation art into solo tracks
                            cover_url = (
                                f"https://coverartarchive.org/release/{album_id}/front-500"
                                if (album_id and rel_score >= 0)
                                else None
                            )

                            meta = TrackMetadata(
                                title=title or "Unknown Title",
                                artist=artist_name,
                                artists=artist_list,
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
                            artists=artist_list,
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
                artist_list = [
                    (
                        a.get("name")
                        or (
                            a.get("artist", {}).get("name")
                            if isinstance(a.get("artist"), dict)
                            else None
                        )
                        or ""
                    ).strip()
                    if isinstance(a, dict)
                    else str(a).strip()
                    for a in artists
                ]
                artist_list = [a for a in artist_list if a]
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
                album_name = "Unknown Album"
                album_id = None
                date = None
                cover_url = None

                if releases:
                    scored_releases = [(score_release(r, artist_name), r) for r in releases]
                    scored_releases.sort(key=lambda x: x[0], reverse=True)
                    best_score, best_rel = scored_releases[0]
                    album_name = best_rel.get("title", "Unknown Album")
                    album_id = best_rel.get("id")
                    date = best_rel.get("date")
                    if album_id and best_score >= 0:
                        cover_url = f"https://coverartarchive.org/release/{album_id}/front-500"

                results.append(
                    TrackMetadata(
                        title=title,
                        artist=artist_name,
                        artists=artist_list,
                        album=album_name,
                        date=date,
                        isrc=isrc,
                        musicbrainz_trackid=mbid,
                        musicbrainz_albumid=album_id,
                        cover_art_url=cover_url,
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
                artist_list = [
                    (
                        c.get("name")
                        or (
                            c.get("artist", {}).get("name")
                            if isinstance(c.get("artist"), dict)
                            else None
                        )
                        or ""
                    ).strip()
                    if isinstance(c, dict)
                    else str(c).strip()
                    for c in credits
                ]
                artist_list = [a for a in artist_list if a]
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
                album_name = "Unknown Album"
                album_id = None
                date = None
                cover_url = None

                if releases:
                    scored_releases = [(score_release(r, artist_name), r) for r in releases]
                    scored_releases.sort(key=lambda x: x[0], reverse=True)
                    best_score, best_rel = scored_releases[0]
                    album_name = best_rel.get("title", "Unknown Album")
                    album_id = best_rel.get("id")
                    date = best_rel.get("date")
                    if album_id and best_score >= 0:
                        cover_url = f"https://coverartarchive.org/release/{album_id}/front-500"

                results.append(
                    TrackMetadata(
                        title=rec_title,
                        artist=artist_name,
                        artists=artist_list,
                        album=album_name,
                        date=date,
                        musicbrainz_trackid=rec.get("id"),
                        musicbrainz_albumid=album_id,
                        cover_art_url=cover_url,
                        confidence_score=score,
                        source_provider=self.name,
                    )
                )
            return results
        except Exception:
            return []
