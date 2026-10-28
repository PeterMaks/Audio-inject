"""Unit tests for MP3 scanning and ID3v2 metadata / APIC cover art injection."""

from pathlib import Path

import pytest
from mutagen.id3 import ID3
from mutagen.mp3 import MP3

from flac_injector.models import TrackMetadata
from flac_injector.scanner import inspect_audio
from flac_injector.writer import InjectionError, inject_metadata
from tests.conftest import create_dummy_image_bytes, generate_mp3_audio


def test_inspect_untagged_mp3(untagged_mp3: Path) -> None:
    """Test inspecting a synthetic untagged MP3 audio file."""
    res = inspect_audio(untagged_mp3)

    assert res.path == untagged_mp3.resolve()
    assert res.audio_format == "mp3"
    assert 1.8 <= res.duration_seconds <= 2.2
    assert res.sample_rate == 44100
    assert res.has_cover_art is False
    assert res.is_incomplete is True
    assert "TITLE" in res.missing_fields
    assert "ARTIST" in res.missing_fields


def test_inject_metadata_into_mp3(tmp_path: Path) -> None:
    """Test injecting complete canonical ID3 frames and APIC artwork into an MP3 file."""
    mp3_file = tmp_path / "daft_punk.mp3"
    generate_mp3_audio(mp3_file, duration_seconds=2)

    meta = TrackMetadata(
        title="Around the World",
        artist="Daft Punk",
        album="Homework",
        album_artist="Daft Punk",
        track_number="7",
        track_total="16",
        date="1997-01-20",
        genre=["Electronic", "House"],
        isrc="FRZ039600007",
        bpm=121.0,
        explicit=False,
        acoustid_id="test-acoustid-999",
        musicbrainz_trackid="mb-track-888",
    )

    art_bytes = create_dummy_image_bytes(700, 700, "yellow")
    result = inject_metadata(
        mp3_file,
        meta,
        cover_art_bytes=art_bytes,
        cover_art_mime="image/jpeg",
    )

    assert result["status"] == "success"
    assert result["format"] == "mp3"
    assert "TIT2" in result["tags_injected"]
    assert result["cover_art_injected"] is True

    # Verify directly using Mutagen ID3
    audio = MP3(str(mp3_file), ID3=ID3)
    assert audio.tags is not None
    assert audio.tags["TIT2"].text == ["Around the World"]
    assert audio.tags["TPE1"].text == ["Daft Punk"]
    assert audio.tags["TALB"].text == ["Homework"]
    assert audio.tags["TRCK"].text == ["7/16"]
    assert [str(t) for t in audio.tags["TDRC"].text] == ["1997-01-20"]
    assert audio.tags["TBPM"].text == ["121"]
    assert audio.tags["TSRC"].text == ["FRZ039600007"]

    # Verify APIC cover art
    apic_frames = [f for k, f in audio.tags.items() if k.startswith("APIC")]
    assert len(apic_frames) == 1
    assert apic_frames[0].type == 3
    assert apic_frames[0].mime == "image/jpeg"
    assert len(apic_frames[0].data) == len(art_bytes)

    # Test inspect_audio on the newly tagged MP3
    scan = inspect_audio(mp3_file)
    assert scan.audio_format == "mp3"
    assert scan.is_incomplete is False
    assert scan.has_cover_art is True
    assert scan.cover_art_info["width"] == 700
    assert scan.existing_tags["TITLE"] == ["Around the World"]
    assert scan.existing_tags["ARTIST"] == ["Daft Punk"]
    assert scan.existing_tags["ALBUM"] == ["Homework"]
    assert scan.existing_tags["TRACKNUMBER"] == ["7"]


def test_mp3_overwrite_behavior(tmp_path: Path) -> None:
    """Test overwrite_existing flag when modifying MP3 tags."""
    mp3_file = tmp_path / "preserve_test.mp3"
    generate_mp3_audio(mp3_file, duration_seconds=2)

    meta1 = TrackMetadata(title="Original Title", artist="Original Artist", album="Album A")
    inject_metadata(mp3_file, meta1)

    # Attempt to inject new title without overwrite
    meta2 = TrackMetadata(title="New Title", artist="Original Artist", album="Album B")
    inject_metadata(mp3_file, meta2, overwrite_existing=False)

    audio = MP3(str(mp3_file))
    assert audio.tags["TIT2"].text == ["Original Title"]

    # Now inject with overwrite=True
    inject_metadata(mp3_file, meta2, overwrite_existing=True)
    audio = MP3(str(mp3_file))
    assert audio.tags["TIT2"].text == ["New Title"]
    assert audio.tags["TALB"].text == ["Album B"]


def test_inject_wav_fails_with_instruction(untagged_wav: Path) -> None:
    """Test that attempting to inject tags into WAV raises InjectionError with convert advice."""
    meta = TrackMetadata(title="Test", artist="Test", album="Test")
    with pytest.raises(InjectionError, match="convert"):
        inject_metadata(untagged_wav, meta)


def test_inject_multi_artist_mp3(tmp_path: Path) -> None:
    """Test that multiple collaborating artists are injected as distinct ID3 TPE1 entries."""
    mp3_file = tmp_path / "collab.mp3"
    generate_mp3_audio(mp3_file, duration_seconds=2)

    meta = TrackMetadata(
        title="Stay",
        artist="The Kid LAROI, Justin Bieber",
        album="F*CK LOVE 3: OVERKILL",
    )

    assert meta.artists == ["The Kid LAROI", "Justin Bieber"]
    id3_dict = meta.to_id3_dict()
    assert id3_dict["TPE1"] == ["The Kid LAROI", "Justin Bieber"]
    assert id3_dict["TPE2"] == "The Kid LAROI"

    result = inject_metadata(mp3_file, meta, overwrite_existing=True)
    assert result["status"] == "success"

    audio = MP3(str(mp3_file), ID3=ID3)
    assert audio.tags["TPE1"].text == ["The Kid LAROI", "Justin Bieber"]
    assert audio.tags["TPE2"].text == ["The Kid LAROI"]

    scan = inspect_audio(mp3_file)
    assert scan.existing_tags["ARTIST"] == ["The Kid LAROI", "Justin Bieber"]
