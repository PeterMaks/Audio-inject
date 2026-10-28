"""Audio conversion engine converting uncompressed / WAV audio files to FLAC using FFmpeg."""

import shutil
import subprocess
from pathlib import Path
from typing import Any

from mutagen.flac import FLAC, FLACNoHeaderError

from flac_injector.subprocess_patch import (
    get_windows_headless_kwargs,
    install_windows_headless_subprocess_patch,
)

# Install Windows headless patch globally before any child process invocation
install_windows_headless_subprocess_patch()


def run_silent_subprocess(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Run subprocess with silent headless flags on Windows."""
    headless_kwargs = get_windows_headless_kwargs()
    for k, v in headless_kwargs.items():
        if k not in kwargs:
            kwargs[k] = v
    return subprocess.run(args, **kwargs)


class ConversionError(Exception):
    """Raised when audio conversion fails."""


def find_ffmpeg_binary() -> str:
    """Find ffmpeg binary in system PATH or WinGet package directories."""
    bin_path = shutil.which("ffmpeg")
    if bin_path:
        return bin_path

    # Check Windows WinGet package installations
    winget_packages = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    if winget_packages.is_dir():
        for candidate in winget_packages.glob("**/ffmpeg.exe"):
            if candidate.is_file():
                return str(candidate)

    return "ffmpeg"


def convert_to_flac(
    input_path: Path | str,
    output_path: Path | str | None = None,
    delete_original: bool = False,
    compression_level: int = 8,
) -> Path:
    """Convert an audio file (e.g. WAV, AIFF) to lossless FLAC format using FFmpeg."""
    src = Path(input_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Input audio file not found: {src}")

    # Determine destination FLAC path
    if output_path is None:
        dest = src.with_suffix(".flac")
    else:
        dest = Path(output_path).resolve()
        if dest.is_dir() or not dest.suffix:
            dest = dest / f"{src.stem}.flac"
        elif dest.suffix.lower() != ".flac":
            dest = dest.with_suffix(".flac")

    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = find_ffmpeg_binary()

    # Build FFmpeg command for bit-perfect FLAC encoding
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(src),
        "-c:a",
        "flac",
        "-compression_level",
        str(max(0, min(12, compression_level))),
        str(dest),
    ]

    try:
        proc = run_silent_subprocess(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if proc.returncode != 0:
            err_msg = proc.stderr.strip()[:200]
            raise ConversionError(
                f"FFmpeg conversion failed for {src.name} with code {proc.returncode}: {err_msg}"
            )
    except FileNotFoundError as e:
        raise ConversionError(
            f"FFmpeg binary '{ffmpeg_bin}' was not found. Please install ffmpeg."
        ) from e
    except Exception as e:
        if not isinstance(e, ConversionError):
            raise ConversionError(f"Unexpected error during conversion of {src.name}: {e}") from e
        raise

    # Verify converted FLAC file integrity with Mutagen
    try:
        audio = FLAC(str(dest))
        if getattr(audio.info, "length", 0) <= 0:
            raise ConversionError(f"Converted file has invalid duration: {dest}")
    except FLACNoHeaderError as e:
        raise ConversionError(f"Converted file is not a valid FLAC audio file: {dest}") from e

    # Optionally delete source file if conversion succeeded and paths differ
    if delete_original and src != dest and src.exists():
        src.unlink()

    return dest
