"""AcoustID / Chromaprint audio fingerprinting and fallback filepath parser."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from flac_injector.config import get_settings
from flac_injector.models import FingerprintResult
from flac_injector.subprocess_patch import (
    get_windows_headless_kwargs,
    install_windows_headless_subprocess_patch,
)

# Install Windows headless patch globally before any acoustid or child process invocation
install_windows_headless_subprocess_patch()


def run_silent_subprocess(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Run subprocess with silent headless flags on Windows."""
    headless_kwargs = get_windows_headless_kwargs()
    for k, v in headless_kwargs.items():
        if k not in kwargs:
            kwargs[k] = v
    return subprocess.run(args, **kwargs)


class FingerprintError(Exception):
    """Raised when audio fingerprint generation fails."""


def generate_fingerprint(
    file_path: Path | str,
    fpcalc_path: str | None = None,
) -> FingerprintResult:
    """Generate Chromaprint fingerprint and duration from an audio file.

    Tries fpcalc binary first, falls back to pyacoustid library if available.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    settings = get_settings()
    binary = fpcalc_path or settings.fpcalc_path

    # Check if fpcalc is available in PATH or specified directly
    fpcalc_bin = shutil.which(binary) or (Path(binary).exists() and binary)

    if not fpcalc_bin:
        winget_packages = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
        if winget_packages.is_dir():
            for candidate in winget_packages.glob("**/fpcalc.exe"):
                if candidate.is_file():
                    fpcalc_bin = str(candidate)
                    break

    if fpcalc_bin:
        try:
            cmd = [str(fpcalc_bin), "-json", str(path)]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
                **get_windows_headless_kwargs(),
            )
            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                duration = float(data.get("duration", 0.0))
                fingerprint = str(data.get("fingerprint", ""))
                if fingerprint:
                    return FingerprintResult(fingerprint=fingerprint, duration=duration)
        except Exception:
            pass

    # Fallback to pyacoustid (uses subprocess.Popen internally).
    # The global Popen monkey-patch adds CREATE_NO_WINDOW + SW_HIDE; re-apply
    # it here in case a frozen PyInstaller build lost the patch.
    try:
        install_windows_headless_subprocess_patch()
        import acoustid

        duration, fingerprint = acoustid.fingerprint_file(str(path))
        return FingerprintResult(
            fingerprint=fingerprint.decode("utf-8")
            if isinstance(fingerprint, bytes)
            else str(fingerprint),
            duration=float(duration),
        )
    except Exception as e:
        raise FingerprintError(f"Failed to generate fingerprint for {path}: {e}") from e


def parse_filename_metadata(file_path: Path | str) -> dict[str, Any]:
    """Parse candidate track metadata from file name and directory hierarchy."""
    path = Path(file_path).resolve()
    stem = path.stem.strip()

    result: dict[str, Any] = {
        "title": None,
        "artist": None,
        "album": None,
        "track_number": None,
    }

    # Clean stem of leading/trailing underscores and multiple spaces
    cleaned_stem = re.sub(r"_+", " ", stem).strip()
    cleaned_stem = re.sub(r"\s+", " ", cleaned_stem)

    # 1. Pattern: "01 - Artist - Title" or "01. Artist - Title"
    match = re.match(
        r"^(\d{1,3})[\s.\-_]+([^-]+)-([^-]+)$",
        cleaned_stem,
    )
    if match:
        result["track_number"] = match.group(1).lstrip("0") or "1"
        result["artist"] = match.group(2).strip()
        result["title"] = match.group(3).strip()
        _infer_album_from_parent(path, result)
        return result

    # 2. Pattern: "Artist - Title"
    match = re.match(r"^([^-]+)-([^-]+)$", cleaned_stem)
    if match:
        # Check if first part is a track number like "01"
        first = match.group(1).strip()
        second = match.group(2).strip()
        if first.isdigit():
            result["track_number"] = first.lstrip("0") or "1"
            result["title"] = second
        else:
            result["artist"] = first
            result["title"] = second
        _infer_album_from_parent(path, result)
        return result

    # 3. Pattern: "01. Title" or "01 Title"
    match = re.match(r"^(\d{1,3})[\s.\-_]+(.*)$", cleaned_stem)
    if match:
        result["track_number"] = match.group(1).lstrip("0") or "1"
        result["title"] = match.group(2).strip()
        _infer_album_from_parent(path, result)
        return result

    # 4. Fallback: stem is the title
    result["title"] = cleaned_stem
    _infer_album_from_parent(path, result)
    return result


GENERIC_DIRS = {
    "fixtures", "tests", "test", "music", "flac", "audio", "downloads",
    "desktop", "documents", "temp", "tmp", "source", "src", "bin"
}


def _infer_album_from_parent(path: Path, result: dict[str, Any]) -> None:
    """Infer album and artist from parent directory structure if not already populated."""
    parent = path.parent
    parent_name = parent.name.strip()
    grandparent_name = parent.parent.name.strip()

    # Pattern: "Artist - Album" in parent folder
    if " - " in parent_name:
        parts = parent_name.split(" - ", 1)
        if not result["artist"]:
            result["artist"] = parts[0].strip()
        if not result["album"]:
            result["album"] = parts[1].strip()
    else:
        # Avoid treating generic container folders as album names
        if parent_name.lower() in GENERIC_DIRS:
            return

        # Pattern: Artist/Album hierarchy
        if not result["album"] and parent_name:
            result["album"] = parent_name
        if (
            not result["artist"]
            and grandparent_name
            and grandparent_name.lower() not in GENERIC_DIRS
        ):
            result["artist"] = grandparent_name
