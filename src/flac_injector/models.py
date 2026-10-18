"""Canonical Pydantic models for FLAC metadata inspection, fingerprinting, and injection."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TrackMetadata(BaseModel):
    """Canonical representation of track metadata aggregated across providers."""

    title: str
    artist: str
    album: str
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
            clean_vals = [v.strip() for v in vals if v and v.strip()]
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


class ScanResult(BaseModel):
    """Result of inspecting a local FLAC file for metadata completeness."""

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


class FingerprintResult(BaseModel):
    """Result of acoustic fingerprinting via Chromaprint/AcoustID."""

    fingerprint: str
    duration: float
