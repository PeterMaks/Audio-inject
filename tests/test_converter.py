"""Unit tests for converter.py audio conversion from WAV to FLAC."""

from pathlib import Path

import pytest
from mutagen.flac import FLAC

from flac_injector.converter import ConversionError, convert_to_flac, find_ffmpeg_binary
from tests.conftest import generate_wav_audio


def test_find_ffmpeg_binary() -> None:
    """Test that find_ffmpeg_binary locates ffmpeg on the system."""
    binary = find_ffmpeg_binary()
    assert binary is not None
    assert "ffmpeg" in binary.lower()


def test_convert_wav_to_flac_default(untagged_wav: Path, tmp_path: Path) -> None:
    """Test converting a synthetic WAV file to FLAC in the same folder."""
    # Create isolated copy of wav
    wav_copy = tmp_path / "track_to_convert.wav"
    generate_wav_audio(wav_copy, duration_seconds=2)

    flac_path = convert_to_flac(wav_copy)
    assert flac_path.is_file()
    assert flac_path.suffix == ".flac"
    assert flac_path.stem == "track_to_convert"

    # Verify converted FLAC using Mutagen
    audio = FLAC(str(flac_path))
    assert 1.8 <= audio.info.length <= 2.2
    assert audio.info.sample_rate == 44100

    # Ensure source was NOT deleted by default
    assert wav_copy.is_file()


def test_convert_wav_custom_output_dir(tmp_path: Path) -> None:
    """Test converting WAV to FLAC into a specific output directory."""
    wav_file = tmp_path / "song.wav"
    generate_wav_audio(wav_file, duration_seconds=2)

    out_dir = tmp_path / "output_flacs"
    flac_path = convert_to_flac(wav_file, output_path=out_dir)

    assert flac_path.parent == out_dir
    assert flac_path.name == "song.flac"
    assert flac_path.is_file()


def test_convert_wav_delete_original(tmp_path: Path) -> None:
    """Test converting WAV to FLAC with delete_original=True."""
    wav_file = tmp_path / "transient.wav"
    generate_wav_audio(wav_file, duration_seconds=2)

    flac_path = convert_to_flac(wav_file, delete_original=True)
    assert flac_path.is_file()
    # Source WAV should now be unlinked
    assert not wav_file.exists()


def test_convert_nonexistent_file(tmp_path: Path) -> None:
    """Test that converting a missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        convert_to_flac(tmp_path / "does_not_exist.wav")


def test_convert_corrupted_file(tmp_path: Path) -> None:
    """Test that converting a corrupted non-audio file raises ConversionError."""
    fake_file = tmp_path / "corrupted.wav"
    fake_file.write_bytes(b"NOT_A_VALID_WAV_HEADER_DATA_123456789")

    with pytest.raises(ConversionError):
        convert_to_flac(fake_file)
