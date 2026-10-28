"""Tests for multi-artist splitting, compound artist guarding, and metadata serialization."""

from flac_injector.merger import aggregate_candidates
from flac_injector.models import TrackMetadata, split_artists


def test_split_artists_delimiters() -> None:
    """Test splitting on comma, semicolon, slash, feat, ft, &, and x."""
    assert split_artists("Daft Punk, Pharrell Williams") == ["Daft Punk", "Pharrell Williams"]
    assert split_artists("Drake; 21 Savage") == ["Drake", "21 Savage"]
    assert split_artists("Linkin Park / Jay-Z") == ["Linkin Park", "Jay-Z"]
    assert split_artists("Calvin Harris feat. Ellie Goulding") == [
        "Calvin Harris",
        "Ellie Goulding",
    ]
    assert split_artists("Skrillex ft. Justin Bieber") == ["Skrillex", "Justin Bieber"]
    assert split_artists("Major Lazer featuring MO") == ["Major Lazer", "MO"]
    assert split_artists("David Guetta with Sia") == ["David Guetta", "Sia"]
    assert split_artists("Marshmello & Khalid") == ["Marshmello", "Khalid"]
    assert split_artists("Major Lazer x DJ Snake") == ["Major Lazer", "DJ Snake"]
    assert split_artists("David Guetta vs. Morten") == ["David Guetta", "Morten"]


def test_split_artists_compound_protection() -> None:
    """Test that compound artist names are never split."""
    assert split_artists("Earth, Wind & Fire") == ["Earth, Wind & Fire"]
    assert split_artists("Tyler, The Creator") == ["Tyler, The Creator"]
    assert split_artists("AC/DC") == ["AC/DC"]
    assert split_artists("Simon & Garfunkel") == ["Simon & Garfunkel"]
    assert split_artists("Crosby, Stills, Nash & Young") == ["Crosby, Stills, Nash & Young"]
    assert split_artists("Hall & Oates") == ["Hall & Oates"]
    assert split_artists("Kool & The Gang") == ["Kool & The Gang"]
    assert split_artists("Florence + The Machine") == ["Florence + The Machine"]
    assert split_artists("Bob Marley & The Wailers") == ["Bob Marley & The Wailers"]


def test_split_artists_compound_in_collaboration() -> None:
    """Test compound artist collaborating with another artist."""
    res1 = split_artists("Tyler, The Creator feat. A$AP Rocky")
    assert res1 == ["Tyler, The Creator", "A$AP Rocky"]

    res2 = split_artists("Earth, Wind & Fire & Ramsey Lewis")
    assert res2 == ["Earth, Wind & Fire", "Ramsey Lewis"]

    res3 = split_artists("AC/DC, Guns N' Roses")
    assert res3 == ["AC/DC", "Guns N' Roses"]

    res4 = split_artists("Simon & Garfunkel / Bob Dylan")
    assert res4 == ["Simon & Garfunkel", "Bob Dylan"]


def test_split_artists_list_input_and_deduplication() -> None:
    """Test list inputs, deduplication preserving order, and edge cases."""
    assert split_artists(["Daft Punk", "Pharrell Williams"]) == ["Daft Punk", "Pharrell Williams"]
    assert split_artists(["Drake, 21 Savage", "Travis Scott"]) == [
        "Drake",
        "21 Savage",
        "Travis Scott",
    ]
    assert split_artists(["Daft Punk", "Daft Punk", "Pharrell Williams"]) == [
        "Daft Punk",
        "Pharrell Williams",
    ]
    assert split_artists("") == []
    assert split_artists(None) == []


def test_track_metadata_multi_artist_serialization() -> None:
    """Test that TrackMetadata properly populates artists and serializes to Vorbis and ID3."""
    meta = TrackMetadata(
        title="Get Lucky",
        artist="Daft Punk, Pharrell Williams & Nile Rodgers",
        album="Random Access Memories",
    )

    assert meta.artists == ["Daft Punk", "Pharrell Williams", "Nile Rodgers"]
    assert meta.get_artists() == ["Daft Punk", "Pharrell Williams", "Nile Rodgers"]

    vorbis = meta.to_vorbis_comments()
    assert vorbis["ARTIST"] == ["Daft Punk", "Pharrell Williams", "Nile Rodgers"]
    assert vorbis["ALBUMARTIST"] == ["Daft Punk"]

    id3 = meta.to_id3_dict()
    assert id3["TPE1"] == ["Daft Punk", "Pharrell Williams", "Nile Rodgers"]
    assert id3["TPE2"] == "Daft Punk"


def test_merger_enriches_artists_from_more_detailed_candidate() -> None:
    """Test that candidate with multi-artist list enriches single-artist candidate."""
    c1 = TrackMetadata(
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        confidence_score=0.95,
        source_provider="itunes",
    )
    c2 = TrackMetadata(
        title="Get Lucky",
        artist="Daft Punk, Pharrell Williams",
        album="Random Access Memories",
        confidence_score=0.90,
        source_provider="spotify",
    )

    merged = aggregate_candidates(
        [c1, c2], file_duration=248.0, hints={"title": "Get Lucky", "artist": "Daft Punk"}
    )
    assert merged is not None
    assert merged.artists == ["Daft Punk", "Pharrell Williams"]
