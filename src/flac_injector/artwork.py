"""Artwork provenance verification, caching, and isolation mechanisms."""

from __future__ import annotations

import re
import string
from pathlib import Path

from rapidfuzz import fuzz

from flac_injector.models import TrackMetadata

# Generic artist and album values that must never be cached or used as sole matching criteria
GENERIC_ARTISTS = {
    "",
    "unknown",
    "unknown artist",
    "various",
    "various artists",
    "various artist",
    "track",
    "artist",
    "soundtrack",
    "ost",
}

GENERIC_ALBUMS = {
    "",
    "unknown",
    "unknown album",
    "untitled",
    "album",
    "greatest hits",
    "singles",
    "the singles",
    "hits",
    "best of",
    "various",
    "various artists",
}


def normalize_text(val: str | None) -> str:
    """Normalize text by stripping whitespace, lowercasing, and removing punctuation."""
    if not val:
        return ""
    text = str(val).lower().strip()
    # Remove punctuation
    translator = str.maketrans("", "", string.punctuation)
    text = text.translate(translator)
    # Collapse multiple whitespace characters into single space
    return re.sub(r"\s+", " ", text).strip()


def is_generic_artist(artist: str | None) -> bool:
    """Check if an artist name is generic or placeholder."""
    return normalize_text(artist) in GENERIC_ARTISTS


def is_generic_album(album: str | None) -> bool:
    """Check if an album title is generic or placeholder."""
    return normalize_text(album) in GENERIC_ALBUMS


def make_artwork_cache_key(
    artist: str | None,
    album: str | None,
    release_id_or_isrc: str | None = None,
) -> tuple[str, str, str] | None:
    """Generate a collision-proof artwork cache key.

    Returns None if the artist or album is generic or missing, which signals
    that caching should be completely bypassed.
    """
    norm_artist = normalize_text(artist)
    if is_generic_artist(norm_artist):
        return None

    norm_album = normalize_text(album)
    if is_generic_album(norm_album) and not release_id_or_isrc:
        return None

    norm_id = normalize_text(release_id_or_isrc) if release_id_or_isrc else ""
    return (norm_artist, norm_album, norm_id)


class ArtworkCache:
    """Thread-safe, collision-proof artwork cache keyed by (artist, album, id)."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, str], tuple[bytes, str]] = {}

    def get(
        self,
        artist: str | None,
        album: str | None,
        release_id_or_isrc: str | None = None,
    ) -> tuple[bytes, str] | None:
        key = make_artwork_cache_key(artist, album, release_id_or_isrc)
        if key is None:
            return None
        return self._cache.get(key)

    def set(
        self,
        artist: str | None,
        album: str | None,
        data: bytes,
        mime: str,
        release_id_or_isrc: str | None = None,
    ) -> None:
        key = make_artwork_cache_key(artist, album, release_id_or_isrc)
        if key is None:
            return
        self._cache[key] = (data, mime)

    def clear(self) -> None:
        self._cache.clear()


def verify_artwork_candidate(
    track_meta: TrackMetadata,
    candidate_artist: str,
    candidate_album: str,
    candidate_title: str,
    candidate_isrc: str | None = None,
) -> bool:
    """Strict artwork candidate verification gate using RapidFuzz.

    Guarantees:
    1. Artist Similarity Gate: RapidFuzz token_set_ratio >= 80 between track artist
       and candidate artist. Disallows generic artists.
    2. Album / Title Gate:
       - If track_meta.album is present and not generic: requires token_set_ratio >= 75
         OR exact ISRC match.
       - If track_meta.album is missing/generic: requires token_set_ratio >= 85 on title,
         and ensures candidate is not a generic compilation.
    """
    # 1. Reject generic artists immediately
    if is_generic_artist(track_meta.artist) or is_generic_artist(candidate_artist):
        return False

    norm_track_artist = normalize_text(track_meta.artist)
    norm_cand_artist = normalize_text(candidate_artist)

    # Artist Similarity Gate (>= 80)
    artist_similarity = fuzz.token_set_ratio(norm_track_artist, norm_cand_artist)
    if artist_similarity < 80:
        return False

    # ISRC exact match bypasses album name differences
    if (
        track_meta.isrc
        and candidate_isrc
        and track_meta.isrc.strip().upper() == candidate_isrc.strip().upper()
    ):
        return True

    # 2. Album / Title Gate
    if track_meta.album and not is_generic_album(track_meta.album):
        norm_track_album = normalize_text(track_meta.album)
        norm_cand_album = normalize_text(candidate_album)
        album_similarity = fuzz.token_set_ratio(norm_track_album, norm_cand_album)
        return album_similarity >= 75
    else:
        # Album missing or generic: require high title similarity
        norm_track_title = normalize_text(track_meta.title)
        norm_cand_title = normalize_text(candidate_title)
        title_similarity = fuzz.token_set_ratio(norm_track_title, norm_cand_title)
        if title_similarity < 85:
            return False

        # Reject compilations when track album is missing
        if candidate_album:
            norm_cand_album = normalize_text(candidate_album)
            if any(
                p in norm_cand_album
                for p in (
                    "compilation",
                    "soundtrack",
                    "greatest hits",
                    "best of",
                    "various artists",
                )
            ):
                return False

        return True


def resolve_local_folder_art(audio_file: Path) -> Path | None:
    """Find local folder cover image if and only if the folder belongs to a single artist/album.

    Disables local folder art fallback when a directory contains tracks from multiple
    distinct artists or differing ALBUM tags, preventing flat folder bleed.
    """
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3

    parent = audio_file.parent
    if not parent.is_dir():
        return None

    audio_files = [
        f for f in parent.iterdir() if f.is_file() and f.suffix.lower() in {".flac", ".mp3"}
    ]
    if not audio_files:
        return None

    seen_artists: set[str] = set()
    seen_albums: set[str] = set()

    for af in audio_files:
        try:
            if af.suffix.lower() == ".flac":
                audio = FLAC(str(af))
                artist = audio.get("ARTIST", [""])[0]
                album = audio.get("ALBUM", [""])[0]
            else:
                audio = MP3(str(af))
                artist = str(audio.get("TPE1", ""))
                album = str(audio.get("TALB", ""))

            norm_a = normalize_text(artist)
            norm_al = normalize_text(album)
            if norm_a and not is_generic_artist(norm_a):
                seen_artists.add(norm_a)
            if norm_al and not is_generic_album(norm_al):
                seen_albums.add(norm_al)
        except Exception:
            continue

    # If the folder has tracks from multiple distinct artists or albums, disable fallback
    if len(seen_artists) > 1 or len(seen_albums) > 1:
        return None

    loose_art_names = {
        "folder.jpg",
        "folder.png",
        "cover.jpg",
        "cover.png",
        "albumart.jpg",
        "albumart.png",
        "front.jpg",
        "front.png",
    }
    for item in parent.iterdir():
        if item.is_file() and item.name.lower() in loose_art_names:
            return item

    return None
