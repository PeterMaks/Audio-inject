"""Async JSON-Lines IPC bridge for flac-meta-injector.

Used by the Tauri v2 Rust backend to execute operations and stream real-time
progress events to the desktop interface.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import shutil
import sys
import warnings
from pathlib import Path
from typing import Any

from flac_injector.subprocess_patch import install_windows_headless_subprocess_patch

# Ensure all child subprocesses on Windows are silent and detached from console
install_windows_headless_subprocess_patch()

from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from flac_injector.artwork import ArtworkCache
from flac_injector.config import get_settings
from flac_injector.converter import convert_to_flac, find_ffmpeg_binary
from flac_injector.fingerprint import generate_fingerprint, parse_filename_metadata
from flac_injector.merger import aggregate_candidates
from flac_injector.models import ScanResult, TrackMetadata
from flac_injector.providers.apple_itunes import AppleITunesProvider
from flac_injector.providers.deezer import DeezerProvider
from flac_injector.providers.discogs import DiscogsProvider
from flac_injector.providers.musicbrainz import MusicBrainzProvider
from flac_injector.providers.songlink import SonglinkProvider
from flac_injector.providers.spotify import SpotifyProvider
from flac_injector.scanner import inspect_audio, scan_path
from flac_injector.spotify_import import load_spotify_data, match_file_to_spotify
from flac_injector.writer import inject_metadata

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if "pytest" not in sys.modules:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    for _h in logging.root.handlers[:]:
        if hasattr(_h, "setStream"):
            _h.setStream(sys.stderr)
warnings.filterwarnings("ignore")


def bootstrap_bundled_binaries() -> None:
    """When frozen via PyInstaller, point PATH and FPCALC_PATH to sibling sidecars."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        # Prepend the directory containing flac-bridge.exe, ffmpeg.exe, and fpcalc.exe to PATH
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{exe_dir}{os.pathsep}{current_path}"

        ext = ".exe" if sys.platform.startswith("win") else ""
        bundled_fpcalc = exe_dir / f"fpcalc{ext}"
        bundled_ffmpeg = exe_dir / f"ffmpeg{ext}"

        if bundled_fpcalc.exists():
            os.environ["FPCALC_PATH"] = str(bundled_fpcalc)
            os.environ["FPCALC"] = str(bundled_fpcalc)  # Used by pyacoustid
        if bundled_ffmpeg.exists():
            os.environ["FFMPEG_PATH"] = str(bundled_ffmpeg)


bootstrap_bundled_binaries()


def emit_event(event: dict[str, Any]) -> None:
    """Print a single newline-delimited JSON object to stdout and flush."""
    try:
        line = json.dumps(event, ensure_ascii=False)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except Exception as exc:
        sys.stderr.write(f"Failed to serialize event: {exc}\n")
        sys.stderr.flush()


def emit_progress(
    stage: str,
    file: str,
    percent: float,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a standardized progress event."""
    payload: dict[str, Any] = {
        "type": "progress",
        "stage": stage,
        "file": file,
        "percent": round(percent, 1),
        "message": message,
    }
    if extra:
        payload.update(extra)
    emit_event(payload)


def emit_result(action: str, data: Any) -> None:
    """Emit a standardized result event."""
    emit_event({"type": "result", "action": action, "data": data})


def emit_error(message: str, file: str | None = None, action: str | None = None) -> None:
    """Emit a standardized error event."""
    emit_event({
        "type": "error",
        "message": message,
        "file": file,
        "action": action,
    })


def serialize_scan_result(res: ScanResult) -> dict[str, Any]:
    """Convert a ScanResult to a JSON-serializable dictionary."""
    return {
        "path": str(res.path),
        "filename": res.path.name,
        "duration_seconds": res.duration_seconds,
        "sample_rate": res.sample_rate,
        "channels": res.channels,
        "bits_per_sample": res.bits_per_sample,
        "existing_tags": res.existing_tags,
        "missing_fields": res.missing_fields,
        "has_cover_art": res.has_cover_art,
        "cover_art_info": res.cover_art_info,
        "is_incomplete": res.is_incomplete,
        "audio_format": res.audio_format,
    }


def find_fpcalc_binary() -> str | None:
    """Find fpcalc executable path."""
    settings = get_settings()
    binary = settings.fpcalc_path
    found = shutil.which(binary) or (Path(binary).exists() and binary)
    if found:
        return str(found)

    winget_packages = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    if winget_packages.is_dir():
        for candidate in winget_packages.glob("**/fpcalc.exe"):
            if candidate.is_file():
                return str(candidate)

    return None


def run_health_check() -> dict[str, Any]:
    """Inspect system health, toolchains, and credential availability."""
    settings = get_settings()

    ffmpeg_bin: str | None = None
    try:
        ffmpeg_bin = find_ffmpeg_binary()
    except Exception:
        pass

    fpcalc_bin = find_fpcalc_binary()

    acoustid_configured = bool(settings.acoustid_api_key and settings.acoustid_api_key.strip())
    spotify_configured = bool(
        settings.spotify_client_id
        and settings.spotify_client_secret
        and settings.spotify_client_id.strip()
        and settings.spotify_client_secret.strip()
    )
    discogs_configured = bool(settings.discogs_token and settings.discogs_token.strip())
    songlink_configured = bool(settings.songlink_api_key and settings.songlink_api_key.strip())

    return {
        "python_version": sys.version.split()[0],
        "in_venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        "ffmpeg": {
            "available": bool(ffmpeg_bin and Path(ffmpeg_bin).exists()),
            "path": ffmpeg_bin,
        },
        "fpcalc": {
            "available": bool(fpcalc_bin and Path(fpcalc_bin).exists()),
            "path": fpcalc_bin,
        },
        "env_status": {
            "acoustid_configured": acoustid_configured,
            "spotify_configured": spotify_configured,
            "discogs_configured": discogs_configured,
            "songlink_configured": songlink_configured,
            "confidence_threshold": settings.confidence_threshold,
            "cover_art_min_resolution": settings.cover_art_min_resolution,
            "rate_limit_delay": settings.rate_limit_delay,
            "request_timeout": settings.request_timeout,
        },
    }


# rest of file unchanged
