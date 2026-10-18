"""Unit tests for writer.py Vorbis comment and Picture block injection."""

import io
from pathlib import Path

import pytest
from mutagen.flac import FLAC
from PIL import Image

from flac_injector.models import TrackMetadata
from flac_injector.writer import InjectionError, inject_metadata


def _create_dummy_image(width: int = 600, height: int = 600, color: str = "blue") -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_inject_metadata_clean_flac(untagged_flac: Path) -> None:
    """Test injecting complete canonical metadata and cover art into an untagged FLAC."""
    meta = TrackMetadata(
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        track_number="8",
        track_total="13",
        date="2013-05-17",
        genre=["Funk", "Disco"],
        isrc="USQX91300105",
        bpm=116.0,
        explicit=False,
        acoustid_id="test-acoustid-456",
        musicbrainz_trackid="mb-track-456",
    )

    art_bytes = _create_dummy_image(800, 800, "purple")
    result = inject_metadata(
        untagged_flac,
        meta,
        cover_art_bytes=art_bytes,
        cover_art_mime="image/jpeg",
    )

    assert result["status"] == "success"
    assert "TITLE" in result["tags_injected"]
    assert result["cover_art_injected"] is True

    # Verify directly with Mutagen
    audio = FLAC(str(untagged_flac))
    assert audio["TITLE"] == ["Get Lucky"]
    assert audio["ARTIST"] == ["Daft Punk"]
    assert audio["ALBUM"] == ["Random Access Memories"]
    assert audio["TRACKNUMBER"] == ["8"]
    assert audio["BPM"] == ["116"]
    assert audio["ITUNESADVISORY"] == ["2"]  # 2 = clean
    assert audio["ISRC"] == ["USQX91300105"]
    assert audio["GENRE"] == ["Funk", "Disco"]
    assert len(audio.pictures) == 1
    pic = audio.pictures[0]
    assert pic.type == 3
    assert pic.width == 800
    assert pic.height == 800


def test_inject_preserve_existing(partial_flac: Path) -> None:
    """Test that existing tags are preserved when overwrite_existing is False."""
    # partial_flac initially has TITLE = "One More Time"
    new_meta = TrackMetadata(
        title="SHOULD NOT OVERWRITE",
        artist="Daft Punk",
        album="Discovery",
        track_number="1",
    )

    result = inject_metadata(partial_flac, new_meta, overwrite_existing=False)
    assert result["status"] == "success"

    audio = FLAC(str(partial_flac))
    assert audio["TITLE"] == ["One More Time"]  # Preserved!
    assert audio["ARTIST"] == ["Daft Punk"]     # Injected!
    assert audio["ALBUM"] == ["Discovery"]      # Injected!


def test_inject_overwrite_existing(partial_flac: Path) -> None:
    """Test that existing tags are overwritten when overwrite_existing is True."""
    new_meta = TrackMetadata(
        title="Aerodynamic",
        artist="Daft Punk",
        album="Discovery",
    )

    result = inject_metadata(partial_flac, new_meta, overwrite_existing=True)
    assert result["status"] == "success"

    audio = FLAC(str(partial_flac))
    assert audio["TITLE"] == ["Aerodynamic"]


def test_inject_invalid_image(untagged_flac: Path) -> None:
    """Test that injecting corrupted image bytes raises InjectionError."""
    meta = TrackMetadata(
        title="Test",
        artist="Test Artist",
        album="Test Album",
    )

    with pytest.raises(InjectionError):
        inject_metadata(
            untagged_flac,
            meta,
            cover_art_bytes=b"NOT_A_VALID_IMAGE_BYTES",
        )


def test_inject_nonexistent_file(tmp_path: Path) -> None:
    """Test that injecting into a missing file raises FileNotFoundError."""
    meta = TrackMetadata(title="A", artist="B", album="C")
    with pytest.raises(FileNotFoundError):
        inject_metadata(tmp_path / "missing.flac", meta)
