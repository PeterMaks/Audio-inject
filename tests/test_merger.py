"""Unit tests for merger.py and fingerprint heuristic parsing."""

from pathlib import Path

from flac_injector.fingerprint import parse_filename_metadata
from flac_injector.merger import aggregate_candidates, calculate_confidence
from flac_injector.models import TrackMetadata


def test_calculate_confidence_fingerprint() -> None:
    """Test that fingerprint-based match returns high baseline confidence."""
    cand = TrackMetadata(
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        acoustid_id="test-acoustid-123",
        confidence_score=0.96,
        source_provider="musicbrainz",
    )
    score = calculate_confidence(cand, file_duration=248.0, hints={})
    assert score >= 0.92


def test_calculate_confidence_isrc() -> None:
    """Test that verified ISRC match yields high confidence."""
    cand = TrackMetadata(
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        isrc="USQX91300105",
        confidence_score=0.90,
        source_provider="deezer",
    )
    score = calculate_confidence(cand, file_duration=248.0, hints={})
    assert score >= 0.90


def test_calculate_confidence_fuzzy_text() -> None:
    """Test fuzzy textual matching with matching title and artist."""
    cand = TrackMetadata(
        title="Around the World",
        artist="Daft Punk",
        album="Homework",
        confidence_score=0.80,
        source_provider="apple_itunes",
    )
    hints = {
        "title": "Around The World (Radio Edit)",
        "artist": "Daft Punk",
        "album": "Homework",
    }
    score = calculate_confidence(cand, file_duration=240.0, hints=hints)
    assert score >= 0.75


def test_calculate_confidence_duration_penalty() -> None:
    """Test that significant duration discrepancy penalizes confidence score."""
    cand = TrackMetadata(
        title="Strobe",
        artist="deadmau5",
        album="For Lack of a Better Name",
        confidence_score=0.80,
        source_provider="deezer",
    )
    hints = {
        "title": "Strobe",
        "artist": "deadmau5",
        "candidate_duration": 637.0,  # 10m37s album version
    }
    # File is a 200s radio edit
    score = calculate_confidence(cand, file_duration=200.0, hints=hints)
    assert score < 0.60


def test_aggregate_candidates_waterfall() -> None:
    """Test multi-provider waterfall aggregation and attribute reconciliation."""
    mb_cand = TrackMetadata(
        title="Harder, Better, Faster, Stronger",
        artist="Daft Punk",
        album="Discovery",
        musicbrainz_trackid="mb-track-111",
        musicbrainz_albumid="mb-album-222",
        acoustid_id="acoust-333",
        cover_art_url="https://coverartarchive.org/500.jpg",
        cover_art_width=500,
        cover_art_height=500,
        confidence_score=0.95,
        source_provider="musicbrainz",
    )

    deezer_cand = TrackMetadata(
        title="Harder Better Faster Stronger",
        artist="Daft Punk",
        album="Discovery",
        isrc="GBDUW0100055",
        bpm=123.0,
        explicit=False,
        cover_art_url="https://e-cdns-images.dzcdn.net/1000x1000.jpg",
        cover_art_width=1000,
        cover_art_height=1000,
        confidence_score=0.88,
        source_provider="deezer",
    )

    itunes_cand = TrackMetadata(
        title="Harder, Better, Faster, Stronger",
        artist="Daft Punk",
        album="Discovery",
        genre=["Electronic"],
        track_number="4",
        track_total="14",
        cover_art_url="https://is1-ssl.mzstatic.com/3000x3000bb.jpg",
        cover_art_width=3000,
        cover_art_height=3000,
        confidence_score=0.85,
        source_provider="apple_itunes",
    )

    merged = aggregate_candidates(
        [mb_cand, deezer_cand, itunes_cand],
        file_duration=224.0,
        hints={"title": "Harder, Better, Faster, Stronger", "artist": "Daft Punk"},
        confidence_threshold=0.70,
    )

    assert merged is not None
    # Primary identifiers from MusicBrainz
    assert merged.musicbrainz_trackid == "mb-track-111"
    assert merged.acoustid_id == "acoust-333"

    # Enriched from Deezer
    assert merged.bpm == 123.0
    assert merged.explicit is False
    assert merged.isrc == "GBDUW0100055"

    # Enriched from iTunes
    assert merged.genre == ["Electronic"]
    assert merged.track_number == "4"
    assert merged.track_total == "14"

    # Ultra high-res cover art waterfall: picked iTunes 3000x3000
    assert merged.cover_art_width == 3000
    assert merged.cover_art_height == 3000
    assert merged.cover_art_url == "https://is1-ssl.mzstatic.com/3000x3000bb.jpg"


def test_aggregate_candidates_below_threshold() -> None:
    """Test that candidates below threshold return None."""
    poor_cand = TrackMetadata(
        title="Totally Unrelated Song",
        artist="Random Artist",
        album="Random Album",
        confidence_score=0.20,
        source_provider="unknown",
    )
    res = aggregate_candidates(
        [poor_cand],
        file_duration=180.0,
        hints={"title": "Specific Title", "artist": "Specific Artist"},
        confidence_threshold=0.75,
    )
    assert res is None


def test_aggregate_candidates_replaces_unknown_album() -> None:
    """Test that waterfall replaces 'Unknown Album' with a real album from other candidates."""
    mb_cand = TrackMetadata(
        title="OveR",
        artist="Miyu Tomita",
        album="Unknown Album",
        musicbrainz_trackid="mb-track-999",
        confidence_score=0.95,
        source_provider="musicbrainz",
    )
    apple_cand = TrackMetadata(
        title="OveR",
        artist="Miyu Tomita",
        album="OveR - Single",
        cover_art_url="https://example.com/cover3000.jpg",
        cover_art_width=3000,
        cover_art_height=3000,
        confidence_score=0.88,
        source_provider="apple_itunes",
    )

    merged = aggregate_candidates(
        [mb_cand, apple_cand],
        file_duration=210.0,
        hints={"title": "OveR", "artist": "Miyu Tomita"},
        confidence_threshold=0.70,
    )

    assert merged is not None
    assert merged.album == "OveR - Single"  # Successfully replaced Unknown Album!
    assert merged.cover_art_url == "https://example.com/cover3000.jpg"


def test_parse_filename_metadata_patterns() -> None:
    """Test filename heuristic patterns."""
    # Pattern: "01 - Artist - Title"
    res1 = parse_filename_metadata(Path("C:/Music/01 - Daft Punk - One More Time.flac"))
    assert res1["track_number"] == "1"
    assert res1["artist"] == "Daft Punk"
    assert res1["title"] == "One More Time"

    # Pattern: "Artist - Title"
    res2 = parse_filename_metadata(Path("C:/Music/deadmau5 - Strobe.flac"))
    assert res2["artist"] == "deadmau5"
    assert res2["title"] == "Strobe"

    # Pattern: Folder hierarchy "Artist - Album/03 - Title.flac"
    res3 = parse_filename_metadata(Path("C:/Music/Pink Floyd - The Wall/03 - Mother.flac"))
    assert res3["track_number"] == "3"
    assert res3["title"] == "Mother"
    assert res3["artist"] == "Pink Floyd"
    assert res3["album"] == "The Wall"
