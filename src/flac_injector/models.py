"""Canonical Pydantic models for FLAC metadata inspection, fingerprinting, and injection."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

PLACEHOLDER_TAG_VALUES: set[str] = {
    "unknown",
    "unknown album",
    "unknown artist",
    "unknown title",
    "untitled",
    "none",
    "null",
    "no album",
    "no artist",
    "placeholder",
}


def resolve_album_name(
    album: str | None,
    title: str | None = None,
    is_single: bool = False,
    total_tracks: int | str | None = None,
) -> str:
    """Resolve canonical album name:
    1. If data provides an album (from CSV, tag, or provider) that is not a placeholder or single marker, use it.
    2. If it is a single (or album is missing/placeholder/marked 'Single'), label as '{title} - Single'.
    3. If both fail, label as 'Unknown Album'.
    """
    clean_album = str(album).strip() if album is not None else ""
    clean_title = str(title).strip() if title is not None else ""

    album_lower = clean_album.lower().strip("\"'")
    title_lower = clean_title.lower().strip("\"'")

    is_placeholder = not album_lower or album_lower in PLACEHOLDER_TAG_VALUES
    is_single_marker = album_lower in ("single", "the single", "(single)", "- single", "[single]")

    # Check track total for standalone single releases
    is_single_by_tracks = False
    if total_tracks is not None:
        try:
            is_single_by_tracks = int(str(total_tracks).split("/")[0].strip()) == 1
        except (ValueError, TypeError):
            pass

    has_valid_title = bool(clean_title) and title_lower not in PLACEHOLDER_TAG_VALUES
    has_valid_album = bool(clean_album) and not is_placeholder and not is_single_marker

    single_detected = (
        is_single
        or is_single_marker
        or album_lower.endswith(" - single")
        or album_lower.endswith(" (single)")
        or (is_single_by_tracks and album_lower == title_lower)
        or (is_placeholder and has_valid_title)
    )

    if single_detected:
        target_name = clean_title if has_valid_title else (clean_album if has_valid_album else "")
        if target_name:
            if target_name.lower().endswith(" - single") or target_name.lower().endswith(" (single)"):
                return target_name
            return f"{target_name} - Single"

    # 1. Real Album Name from data (as per data provided by CSV / source)
    if has_valid_album:
        return clean_album

    # 2. Labeled Single (if album was placeholder/missing but title exists)
    if has_valid_title:
        return f"{clean_title} - Single"

    # 3. If both fail, fallback to "Unknown Album"
    return "Unknown Album"


class TrackMetadata(BaseModel):
    """Canonical representation of track metadata aggregated across providers."""

    title: str
    artist: str
    album: str = Field(default="Unknown Album")
    album_artist: str | None = None
    track_number: str | None = None
    track_total: str | None = None
    disc_number: str | None = None
    disc_total: str | None = None
    date: str | None = None
    year: str | None = None
    genre: list[str] = Field(default_factory=list)
    isrc: str | None = None
    barcode: str | None = None
    label: str | None = None
    copyright: str | None = None
    composer: str | None = None
    bpm: float | None = None
    explicit: bool | None = None

    # Audio Database Identifiers
    acoustid_id: str | None = None
    musicbrainz_trackid: str | None = None
    musicbrainz_albumid: str | None = None
    musicbrainz_artistid: str | None = None

    # Cover Art
    cover_art_url: str | None = None
    cover_art_bytes: bytes | None = None
    cover_art_mime: str | None = None
    cover_art_width: int | None = None
    cover_art_height: int | None = None

    # Pipeline Provenance & Quality
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_provider: str = "unknown"
    extra_tags: dict[str, str] = Field(default_factory=dict)

    def to_vorbis_comments(self) -> dict[str, list[str]]:
        """Serialize canonical metadata into standardized Vorbis Comment tags."""
        comments: dict[str, list[str]] = {}

        def add_tag(key: str, val: str | None) -> None:
            if val is not None and str(val).strip():
                comments[key.upper()] = [str(val).strip()]

        def add_multi_tag(key: str, vals: list[str]) -> None:
            seen: set[str] = set()
            clean_vals: list[str] = []
            for v in vals:
                if v and str(v).strip():
                    stripped = str(v).strip()
                    if stripped.lower() not in seen:
                        seen.add(stripped.lower())
                        clean_vals.append(stripped)
            if clean_vals:
                comments[key.upper()] = clean_vals

        add_tag("TITLE", self.title)
        add_tag("ARTIST", self.artist)
        add_tag("ALBUM", self.album)
        add_tag("ALBUMARTIST", self.album_artist or self.artist)

        if self.track_number:
            add_tag("TRACKNUMBER", self.track_number)
        if self.track_total:
            add_tag("TRACKTOTAL", self.track_total)
        if self.disc_number:
            add_tag("DISCNUMBER", self.disc_number)
        if self.disc_total:
            add_tag("DISCTOTAL", self.disc_total)

        if self.date:
            add_tag("DATE", self.date)
            # If date contains a 4-digit year, set YEAR as well
            if len(self.date) >= 4 and self.date[:4].isdigit():
                add_tag("YEAR", self.date[:4])
        elif self.year:
            add_tag("DATE", self.year)
            add_tag("YEAR", self.year)

        add_multi_tag("GENRE", self.genre)

        add_tag("ISRC", self.isrc)
        add_tag("BARCODE", self.barcode)
        add_tag("ORGANIZATION", self.label)
        add_tag("LABEL", self.label)
        add_tag("COPYRIGHT", self.copyright)
        add_tag("COMPOSER", self.composer)

        if self.bpm is not None:
            # Round BPM to 1 decimal or integer string
            formatted_bpm = f"{self.bpm:.1f}" if self.bpm % 1 != 0 else f"{int(self.bpm)}"
            add_tag("BPM", formatted_bpm)

        if self.explicit is not None:
            # 1 = Explicit, 2 = Clean, 0 = Unknown/None
            add_tag("ITUNESADVISORY", "1" if self.explicit else "2")

        add_tag("ACOUSTID_ID", self.acoustid_id)
        add_tag("MUSICBRAINZ_TRACKID", self.musicbrainz_trackid)
        add_tag("MUSICBRAINZ_ALBUMID", self.musicbrainz_albumid)
        add_tag("MUSICBRAINZ_ARTISTID", self.musicbrainz_artistid)

        for k, v in self.extra_tags.items():
            if k.upper() not in comments and v.strip():
                comments[k.upper()] = [v.strip()]

        return comments

    def to_id3_dict(self) -> dict[str, Any]:
        """Serialize canonical metadata into ID3 frame representations."""
        frames: dict[str, Any] = {}

        frames["TIT2"] = self.title
        frames["TPE1"] = self.artist
        frames["TALB"] = self.album
        frames["TPE2"] = self.album_artist or self.artist

        if self.track_number:
            frames["TRCK"] = (
                f"{self.track_number}/{self.track_total}"
                if self.track_total
                else str(self.track_number)
            )
        if self.disc_number:
            frames["TPOS"] = (
                f"{self.disc_number}/{self.disc_total}"
                if self.disc_total
                else str(self.disc_number)
            )

        if self.date:
            frames["TDRC"] = str(self.date)
        elif self.year:
            frames["TDRC"] = str(self.year)

        if self.genre:
            seen_genres: set[str] = set()
            clean_genres: list[str] = []
            for g in self.genre:
                if g and str(g).strip():
                    g_strip = str(g).strip()
                    if g_strip.lower() not in seen_genres:
                        seen_genres.add(g_strip.lower())
                        clean_genres.append(g_strip)
            frames["TCON"] = clean_genres

        if self.isrc:
            frames["TSRC"] = str(self.isrc)
        if self.copyright:
            frames["TCOP"] = str(self.copyright)
        if self.composer:
            frames["TCOM"] = str(self.composer)
        if self.label:
            frames["TPUB"] = str(self.label)

        if self.bpm is not None:
            bpm_str = f"{self.bpm:.1f}" if self.bpm % 1 != 0 else f"{int(self.bpm)}"
            frames["TBPM"] = bpm_str

        # User Defined Text frames (TXXX)
        txxx: dict[str, str] = {}
        if self.musicbrainz_trackid:
            txxx["MusicBrainz Track Id"] = self.musicbrainz_trackid
        if self.musicbrainz_albumid:
            txxx["MusicBrainz Album Id"] = self.musicbrainz_albumid
        if self.musicbrainz_artistid:
            txxx["MusicBrainz Artist Id"] = self.musicbrainz_artistid
        if self.acoustid_id:
            txxx["Acoustid Id"] = self.acoustid_id
        if self.barcode:
            txxx["BARCODE"] = self.barcode
        if self.explicit is not None:
            txxx["ITUNESADVISORY"] = "1" if self.explicit else "2"

        frames["TXXX"] = txxx
        return frames


class ScanResult(BaseModel):
    """Result of inspecting a local audio file for metadata completeness."""

    path: Path
    duration_seconds: float
    sample_rate: int
    channels: int
    bits_per_sample: int
    existing_tags: dict[str, list[str]]
    missing_fields: list[str]
    has_cover_art: bool
    cover_art_info: dict[str, Any] | None = None
    is_incomplete: bool
    audio_format: str = "flac"  # "flac", "mp3", "wav"


class FingerprintResult(BaseModel):
    """Result of acoustic fingerprinting via Chromaprint/AcoustID."""

    fingerprint: str
    duration: float

