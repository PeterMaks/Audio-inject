"""Unit and integration tests for scanner.py."""

from pathlib import Path

import pytest

from flac_injector.scanner import FLACScannerError, inspect_flac, scan_path


def test_inspect_untagged_flac(untagged_flac: Path) -> None:
    """Test inspecting an untagged synthetic FLAC audio file."""
    res = inspect_flac(untagged_flac)

    assert res.path == untagged_flac.resolve()
    assert 1.9 <= res.duration_seconds <= 2.1
    assert res.sample_rate == 44100
    assert res.channels in (1, 2)
    assert res.bits_per_sample == 16
    assert res.has_cover_art is False
    assert res.cover_art_info is None
    assert res.is_incomplete is True

    # Essential fields should be flagged as missing
    expected_missing = {"TITLE", "ARTIST", "ALBUM", "TRACKNUMBER", "DATE", "GENRE"}
    assert expected_missing.issubset(set(res.missing_fields))


def test_inspect_tagged_flac(tagged_flac: Path) -> None:
    """Test inspecting a completely tagged FLAC audio file with embedded cover art."""
    res = inspect_flac(tagged_flac)

    assert res.is_incomplete is False
    assert res.has_cover_art is True
    assert res.cover_art_info is not None
    assert res.cover_art_info["width"] == 600
    assert res.cover_art_info["height"] == 600
    assert res.cover_art_info["depth"] == 24
    assert res.cover_art_info["mime"] == "image/jpeg"
    assert res.missing_fields == []
    assert res.existing_tags["TITLE"] == ["Strobe"]
    assert res.existing_tags["ARTIST"] == ["deadmau5"]
    assert res.existing_tags["ALBUM"] == ["For Lack of a Better Name"]


def test_inspect_partial_flac(partial_flac: Path) -> None:
    """Test inspecting a partially tagged FLAC audio file missing artist, album, and art."""
    res = inspect_flac(partial_flac)

    assert res.is_incomplete is True
    assert res.has_cover_art is False
    assert "TITLE" not in res.missing_fields
    assert "ARTIST" in res.missing_fields
    assert "ALBUM" in res.missing_fields


def test_scan_path_directory(fixtures_dir: Path, untagged_flac: Path, tagged_flac: Path) -> None:
    """Test scanning a directory containing multiple FLAC files."""
    results = scan_path(fixtures_dir, recursive=True)
    paths = [r.path for r in results]

    assert untagged_flac.resolve() in paths
    assert tagged_flac.resolve() in paths
    assert len(results) >= 2


def test_inspect_nonexistent_file(tmp_path: Path) -> None:
    """Test that inspect_flac raises FileNotFoundError for missing path."""
    with pytest.raises(FileNotFoundError):
        inspect_flac(tmp_path / "nonexistent.flac")


def test_inspect_invalid_flac(tmp_path: Path) -> None:
    """Test that inspect_flac raises FLACScannerError on corrupted header."""
    corrupted = tmp_path / "corrupted.flac"
    corrupted.write_bytes(b"INVALID_HEADER_DATA_1234567890")

    with pytest.raises(FLACScannerError):
        inspect_flac(corrupted)


def test_inspect_flac_placeholder_album_is_incomplete(tagged_flac: Path) -> None:
    """Test that a track with 'Unknown Album' is flagged as incomplete."""
    from mutagen.flac import FLAC

    audio = FLAC(str(tagged_flac))
    audio["ALBUM"] = ["Unknown Album"]
    audio.save()

    res = inspect_flac(tagged_flac)
    assert "ALBUM" in res.missing_fields
    assert res.is_incomplete is True
