"""Unit tests for writer.py Vorbis comment and Picture block injection."""

import io
from pathlib import Path

import pytest
from mutagen.flac import FLAC
from PIL import Image

from flac_injector.models import TrackMetadata
from flac_injector.writer import InjectionError, clean_embedded_art, inject_metadata


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
    assert audio["ARTIST"] == ["Daft Punk"]  # Injected!
    assert audio["ALBUM"] == ["Discovery"]  # Injected!


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


def test_inject_deduplicates_tags_and_removes_aliases(untagged_flac: Path) -> None:
    """Test that duplicate genres are deduplicated and conflicting aliases removed."""
    # Pre-populate with duplicate genre and legacy alias
    audio = FLAC(str(untagged_flac))
    audio["GENRE"] = ["Electronic", "electronic", "Rock"]
    audio["ALBUM ARTIST"] = ["Old Legacy Artist"]
    audio["TRACK"] = ["01"]
    audio.save()

    meta = TrackMetadata(
        title="Test Track",
        artist="Daft Punk",
        album="Discovery",
        album_artist="Daft Punk",
        track_number="1",
        genre=["Electronic", "electronic", "Dance", "DANCE"],
    )

    inject_metadata(untagged_flac, meta, overwrite_existing=True)

    verified = FLAC(str(untagged_flac))
    assert verified["GENRE"] == ["Electronic", "Dance"]
    assert verified["ALBUMARTIST"] == ["Daft Punk"]
    assert "ALBUM ARTIST" not in verified  # Conflicting legacy alias cleaned
    assert "TRACK" not in verified  # Conflicting legacy alias cleaned


def test_clean_embedded_art_deduplicates_pictures_and_removes_tags(untagged_flac: Path) -> None:
    """Test that clean_embedded_art strips duplicate picture blocks and Vorbis picture comments."""
    from mutagen.flac import Picture

    audio = FLAC(str(untagged_flac))
    img1 = _create_dummy_image(300, 300, "red")
    img2 = _create_dummy_image(600, 600, "green")

    pic1 = Picture()
    pic1.type = 0  # Other
    pic1.data = img1
    pic1.mime = "image/jpeg"

    pic2 = Picture()
    pic2.type = 3  # Front cover
    pic2.data = img2
    pic2.mime = "image/jpeg"

    audio.add_picture(pic1)
    audio.add_picture(pic2)
    audio["METADATA_BLOCK_PICTURE"] = ["base64dummy"]
    audio["COVERART"] = ["dummy"]
    audio.save()

    res = clean_embedded_art(untagged_flac, dry_run=False)
    assert res["pictures_before"] == 2
    assert res["pictures_after"] == 1
    assert "METADATA_BLOCK_PICTURE" in res["legacy_tags_removed"]
    assert "COVERART" in res["legacy_tags_removed"]

    # Verify FLAC only has 1 picture remaining (the front cover)
    verified = FLAC(str(untagged_flac))
    assert len(verified.pictures) == 1
    assert verified.pictures[0].type == 3
    assert "METADATA_BLOCK_PICTURE" not in verified
    assert "COVERART" not in verified


def test_inject_multi_artist_flac(untagged_flac: Path) -> None:
    """Test that multiple collaborating artists are injected as individual Vorbis ARTIST tags."""
    from flac_injector.scanner import inspect_audio

    meta = TrackMetadata(
        title="Get Lucky",
        artist="Daft Punk, Pharrell Williams & Nile Rodgers",
        album="Random Access Memories",
    )

    assert meta.artists == ["Daft Punk", "Pharrell Williams", "Nile Rodgers"]
    vorbis = meta.to_vorbis_comments()
    assert vorbis["ARTIST"] == ["Daft Punk", "Pharrell Williams", "Nile Rodgers"]
    assert vorbis["ALBUMARTIST"] == ["Daft Punk"]

    result = inject_metadata(untagged_flac, meta, overwrite_existing=True)
    assert result["status"] == "success"

    audio = FLAC(str(untagged_flac))
    assert audio["ARTIST"] == ["Daft Punk", "Pharrell Williams", "Nile Rodgers"]
    assert audio["ALBUMARTIST"] == ["Daft Punk"]

    # Verify scanner reads all artists
    scan = inspect_audio(untagged_flac)
    assert scan.existing_tags["ARTIST"] == ["Daft Punk", "Pharrell Williams", "Nile Rodgers"]
