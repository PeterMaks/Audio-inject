"""Pytest fixtures and synthetic audio generators (FLAC, MP3, WAV) using ffmpeg."""

import io
import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from PIL import Image


def get_ffmpeg_binary() -> str:
    """Find ffmpeg executable in system, PATH, or WinGet package directories."""
    bin_path = shutil.which("ffmpeg")
    if bin_path:
        return bin_path

    # Check WinGet package installations
    winget_packages = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    if winget_packages.is_dir():
        for candidate in winget_packages.glob("**/ffmpeg.exe"):
            if candidate.is_file():
                return str(candidate)

    return "ffmpeg"


def generate_flac_audio(output_path: Path, duration_seconds: int = 2) -> Path:
    """Generate a clean, untagged synthetic FLAC audio file using ffmpeg."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration_seconds}",
        "-c:a",
        "flac",
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to create synthetic FLAC: {proc.stderr}")

    audio = FLAC(str(output_path))
    audio.clear()
    audio.clear_pictures()
    audio.save()

    return output_path


def generate_wav_audio(output_path: Path, duration_seconds: int = 2) -> Path:
    """Generate a clean synthetic WAV audio file using ffmpeg."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration_seconds}",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to create synthetic WAV: {proc.stderr}")

    # Ensure clean tags
    try:
        w = WAVE(str(output_path))
        if w.tags:
            w.clear()
            w.save()
    except Exception:
        pass

    return output_path


def generate_mp3_audio(output_path: Path, duration_seconds: int = 2) -> Path:
    """Generate a clean synthetic MP3 audio file using ffmpeg."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_binary()

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration_seconds}",
        "-c:a",
        "libmp3lame",
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to create synthetic MP3: {proc.stderr}")

    audio = MP3(str(output_path))
    if audio.tags:
        audio.tags.clear()
        audio.save()

    return output_path


def create_dummy_image_bytes(width: int = 600, height: int = 600, color: str = "blue") -> bytes:
    """Create JPEG image bytes for mock cover art."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Fixture directory for audio test files."""
    fix_dir = tmp_path_factory.mktemp("audio_fixtures")
    return fix_dir


@pytest.fixture
def untagged_flac(fixtures_dir: Path) -> Path:
    """A clean 2-second FLAC with no Vorbis comments and no Picture block."""
    target = fixtures_dir / "untagged_track.flac"
    return generate_flac_audio(target, duration_seconds=2)


@pytest.fixture
def untagged_wav(fixtures_dir: Path) -> Path:
    """A clean 2-second WAV uncompressed audio file."""
    target = fixtures_dir / "sample_recording.wav"
    return generate_wav_audio(target, duration_seconds=2)


@pytest.fixture
def untagged_mp3(fixtures_dir: Path) -> Path:
    """A clean 2-second MP3 file without tags."""
    target = fixtures_dir / "sample_track.mp3"
    return generate_mp3_audio(target, duration_seconds=2)


@pytest.fixture
def tagged_flac(fixtures_dir: Path) -> Path:
    """A 2-second FLAC with complete Vorbis comments and embedded cover art."""
    target = fixtures_dir / "tagged_track.flac"
    generate_flac_audio(target, duration_seconds=2)

    audio = FLAC(str(target))
    audio["TITLE"] = ["Strobe"]
    audio["ARTIST"] = ["deadmau5"]
    audio["ALBUM"] = ["For Lack of a Better Name"]
    audio["TRACKNUMBER"] = ["07"]
    audio["DATE"] = ["2009-09-22"]
    audio["GENRE"] = ["Progressive House"]

    pic = Picture()
    pic.type = 3
    pic.mime = "image/jpeg"
    pic.desc = "Front Cover"
    pic.width = 600
    pic.height = 600
    pic.depth = 24
    pic.data = create_dummy_image_bytes(600, 600, "green")
    audio.add_picture(pic)
    audio.save()

    return target


@pytest.fixture
def partial_flac(fixtures_dir: Path) -> Path:
    """A 2-second FLAC with only TITLE tag and missing cover art."""
    target = fixtures_dir / "01 - Daft Punk - One More Time.flac"
    generate_flac_audio(target, duration_seconds=2)

    audio = FLAC(str(target))
    audio["TITLE"] = ["One More Time"]
    audio.save()

    return target
