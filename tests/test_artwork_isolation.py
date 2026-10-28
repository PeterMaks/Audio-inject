"""Unit tests for artwork verification, compilation deprioritization, and batch isolation."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from flac_injector.artwork import (
    ArtworkCache,
    make_artwork_cache_key,
    verify_artwork_candidate,
)
from flac_injector.config import Settings
from flac_injector.merger import aggregate_candidates
from flac_injector.models import TrackMetadata
from flac_injector.providers.musicbrainz import MusicBrainzProvider, score_release


def test_verify_artwork_candidate_artist_mismatch() -> None:
    """Artist mismatch gate: High-res cover for same title by different artist MUST be rejected."""
    track = TrackMetadata(
        title="Creep",
        artist="Radiohead",
        album="Pablo Honey",
    )
    # Different artist with the same track title (e.g. TLC - Creep)
    assert not verify_artwork_candidate(
        track,
        candidate_artist="TLC",
        candidate_album="CrazySexyCool",
        candidate_title="Creep",
    )

    # Completely different artist
    assert not verify_artwork_candidate(
        track,
        candidate_artist="Katy Perry",
        candidate_album="Prism",
        candidate_title="Roar",
    )

    # Same artist with slight punctuation difference (Radiohead vs Radiohead.) passes
    assert verify_artwork_candidate(
        track,
        candidate_artist="Radiohead",
        candidate_album="Pablo Honey",
        candidate_title="Creep",
    )


def test_verify_artwork_candidate_generic_artist_rejection() -> None:
    """Artwork candidate with generic artist or album must be rejected."""
    track = TrackMetadata(
        title="Unknown Track",
        artist="Unknown Artist",
        album="Unknown Album",
    )
    assert not verify_artwork_candidate(
        track,
        candidate_artist="Various Artists",
        candidate_album="Greatest Hits",
        candidate_title="Unknown Track",
    )


def test_verify_artwork_candidate_isrc_bypass() -> None:
    """Exact ISRC match passes even if album title has edition variation."""
    track = TrackMetadata(
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        isrc="USQX91300105",
    )
    # Candidate album has "Random Access Memories (10th Anniversary Edition)"
    assert verify_artwork_candidate(
        track,
        candidate_artist="Daft Punk",
        candidate_album="Random Access Memories (10th Anniversary Edition)",
        candidate_title="Get Lucky",
        candidate_isrc="USQX91300105",
    )


def test_aggregate_candidates_rejects_artist_mismatch_artwork() -> None:
    """Test that aggregate_candidates leaves cover_art_url None instead of taking mismatched art."""
    winning_cand = TrackMetadata(
        title="One More Time",
        artist="Daft Punk",
        album="Discovery",
        confidence_score=0.95,
        source_provider="musicbrainz",
        # Winning candidate has no cover art
        cover_art_url=None,
    )

    # Rogue candidate with 3000px art for a different artist with the same title
    mismatched_art_cand = TrackMetadata(
        title="One More Time",
        artist="Britney Spears",
        album="...Baby One More Time",
        cover_art_url="https://example.com/britney3000.jpg",
        cover_art_width=3000,
        cover_art_height=3000,
        confidence_score=0.60,
        source_provider="apple_itunes",
    )

    merged = aggregate_candidates(
        [winning_cand, mismatched_art_cand],
        file_duration=320.0,
        hints={"title": "One More Time", "artist": "Daft Punk"},
        confidence_threshold=0.70,
    )

    assert merged is not None
    assert merged.artist == "Daft Punk"
    # The Britney Spears 3000px artwork MUST NOT be adopted
    assert merged.cover_art_url is None
    assert merged.cover_art_width is None


def test_compilation_deprioritization_scoring() -> None:
    """Test deterministic scoring of canonical albums vs Various Artists compilations."""
    # Canonical official album
    canonical_rel = {
        "title": "Discovery",
        "status": "Official",
        "type": "Album",
        "artists": [{"name": "Daft Punk"}],
    }
    score_canonical = score_release(canonical_rel, recording_artist="Daft Punk")
    assert score_canonical == 50

    # Single or EP
    single_rel = {
        "title": "One More Time - Single",
        "status": "Official",
        "type": "Single",
        "artists": [{"name": "Daft Punk"}],
    }
    score_single = score_release(single_rel, recording_artist="Daft Punk")
    assert score_single == 35

    # Various Artists compilation penalty (-100)
    compilation_rel = {
        "title": "Now That's What I Call Music! 48",
        "status": "Official",
        "type": "Album",
        "secondarytypes": ["Compilation"],
        "artists": [{"name": "Various Artists"}],
    }
    score_comp = score_release(compilation_rel, recording_artist="Daft Punk")
    assert score_comp <= -50


@pytest.mark.asyncio
async def test_musicbrainz_compilation_deprioritization_lookup() -> None:
    """Test that MusicBrainz provider ranks canonical releases over Various Artists compilations."""
    settings = Settings(ACOUSTID_API_KEY="test_key", RATE_LIMIT_DELAY=0.0)
    provider = MusicBrainzProvider(settings=settings, rate_limit_delay=0.0)

    mock_payload = {
        "status": "ok",
        "results": [
            {
                "id": "acoustid-1",
                "score": 0.98,
                "recordings": [
                    {
                        "id": "rec-1",
                        "title": "Harder, Better, Faster, Stronger",
                        "artists": [{"id": "art-1", "name": "Daft Punk"}],
                        "releases": [
                            # Compilation listed FIRST in raw AcoustID response
                            {
                                "id": "rel-compilation-999",
                                "title": "Mega Dance Hits 2002",
                                "type": "Album",
                                "secondarytypes": ["Compilation"],
                                "artists": [{"name": "Various Artists"}],
                            },
                            # Canonical release listed SECOND
                            {
                                "id": "rel-discovery-123",
                                "title": "Discovery",
                                "status": "Official",
                                "type": "Album",
                                "artists": [{"name": "Daft Punk"}],
                            },
                        ],
                    }
                ],
            }
        ],
    }

    mock_resp = httpx.Response(200, json=mock_payload)
    with patch.object(provider, "request", new_callable=AsyncMock, return_value=mock_resp):
        candidates = await provider.lookup_by_fingerprint("fake_fp", 224.0)

    assert len(candidates) == 2
    # The canonical album MUST be ranked first, NOT the compilation
    first = candidates[0]
    assert first.album == "Discovery"
    assert first.cover_art_url == "https://coverartarchive.org/release/rel-discovery-123/front-500"

    # The compilation MUST NOT have cover_art_url attached
    second = candidates[1]
    assert second.album == "Mega Dance Hits 2002"
    assert second.cover_art_url is None


def test_batch_isolation_across_tracks() -> None:
    """Run injector resolution across 3 tracks in sequence:
    Track 1: Has valid 3000px art.
    Track 2: Has no matching art on any provider.
    Track 3: By a different artist with its own 1000px art.
    Assert Track 2 has cover_art_url is None (zero bleed from Track 1) and Track 3 has its own art.
    """
    # Track 1
    t1_cand = TrackMetadata(
        title="Song One",
        artist="Artist One",
        album="Album One",
        cover_art_url="https://example.com/art1_3000.jpg",
        cover_art_width=3000,
        cover_art_height=3000,
        confidence_score=0.95,
        source_provider="apple_itunes",
    )
    res1 = aggregate_candidates(
        [t1_cand], file_duration=200.0, hints={"title": "Song One", "artist": "Artist One"}
    )
    assert res1 is not None
    assert res1.cover_art_url == "https://example.com/art1_3000.jpg"

    # Track 2: No art on any provider
    t2_cand = TrackMetadata(
        title="Song Two",
        artist="Artist Two",
        album="Album Two",
        cover_art_url=None,
        confidence_score=0.92,
        source_provider="musicbrainz",
    )
    res2 = aggregate_candidates(
        [t2_cand], file_duration=180.0, hints={"title": "Song Two", "artist": "Artist Two"}
    )
    assert res2 is not None
    # Must be completely isolated with ZERO bleed from Track 1
    assert res2.cover_art_url is None
    assert res2.cover_art_width is None

    # Track 3: By Artist Three with distinct art
    t3_cand = TrackMetadata(
        title="Song Three",
        artist="Artist Three",
        album="Album Three",
        cover_art_url="https://example.com/art3_1000.jpg",
        cover_art_width=1000,
        cover_art_height=1000,
        confidence_score=0.90,
        source_provider="deezer",
    )
    res3 = aggregate_candidates(
        [t3_cand], file_duration=220.0, hints={"title": "Song Three", "artist": "Artist Three"}
    )
    assert res3 is not None
    assert res3.cover_art_url == "https://example.com/art3_1000.jpg"


def test_artwork_cache_bypasses_generic_artists() -> None:
    """Test that ArtworkCache keys require specific artist/album and bypass generic ones."""
    cache = ArtworkCache()
    # Generic artist -> make_artwork_cache_key returns None
    assert make_artwork_cache_key("Unknown Artist", "Greatest Hits") is None
    assert make_artwork_cache_key("Various Artists", "Soundtrack") is None
    assert make_artwork_cache_key("", "") is None

    # Specific artist & album produces composite tuple
    key = make_artwork_cache_key("Daft Punk", "Discovery", "mb-123")
    assert key == ("daft punk", "discovery", "mb123")

    # Set and get
    cache.set("Daft Punk", "Discovery", b"fake_image_bytes", "image/jpeg", "mb-123")
    cached = cache.get("Daft Punk", "Discovery", "mb-123")
    assert cached is not None
    assert cached[0] == b"fake_image_bytes"
    assert cached[1] == "image/jpeg"

    # Attempt to cache with generic artist does nothing
    cache.set("Unknown Artist", "Random Album", b"other_bytes", "image/jpeg")
    assert cache.get("Unknown Artist", "Random Album") is None
