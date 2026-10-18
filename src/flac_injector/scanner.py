"""FLAC file inspection and missing-tag detection using Mutagen."""

from pathlib import Path
from typing import Any

from mutagen.flac import FLAC, FLACNoHeaderError

from flac_injector.models import ScanResult

# Tags considered essential for a complete music collection
CORE_TAGS = {"TITLE", "ARTIST", "ALBUM"}
RECOMMENDED_TAGS = {"TRACKNUMBER", "DATE", "GENRE"}


class FLACScannerError(Exception):
    """Raised when an error occurs while scanning a FLAC file."""


def inspect_flac(file_path: Path | str) -> ScanResult:
    """Inspect a single FLAC file and return metadata completeness status."""
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        audio = FLAC(str(path))
    except FLACNoHeaderError as e:
        raise FLACScannerError(f"Not a valid FLAC file: {path} ({e})") from e
    except Exception as e:
        raise FLACScannerError(f"Failed to read FLAC metadata from {path}: {e}") from e

    # Extract audio stream information
    info = audio.info
    duration = float(getattr(info, "length", 0.0))
    sample_rate = int(getattr(info, "sample_rate", 0))
    channels = int(getattr(info, "channels", 0))
    bits_per_sample = int(getattr(info, "bits_per_sample", 0))

    # Vorbis comments are case-insensitive in principle, but we normalize to uppercase
    existing_tags: dict[str, list[str]] = {}
    if audio.tags:
        for k, v in audio.tags.items():
            existing_tags[k.upper()] = [str(item).strip() for item in v if str(item).strip()]

    # Detect missing fields
    missing_fields: list[str] = []
    for tag in CORE_TAGS | RECOMMENDED_TAGS:
        if tag not in existing_tags or not existing_tags[tag]:
            # Also check alternative names, e.g. YEAR for DATE
            if tag == "DATE" and "YEAR" in existing_tags and existing_tags["YEAR"]:
                continue
            missing_fields.append(tag)

    # Check for embedded cover art (Type 3 = Front Cover)
    has_cover_art = False
    cover_info: dict[str, Any] | None = None

    if audio.pictures:
        front_pictures = [p for p in audio.pictures if getattr(p, "type", None) == 3]
        target_pic = front_pictures[0] if front_pictures else audio.pictures[0]
        has_cover_art = True
        cover_info = {
            "type": getattr(target_pic, "type", 3),
            "mime": getattr(target_pic, "mime", "unknown"),
            "width": getattr(target_pic, "width", 0),
            "height": getattr(target_pic, "height", 0),
            "depth": getattr(target_pic, "depth", 0),
            "size_bytes": len(getattr(target_pic, "data", b"")),
        }

    # An audio file is incomplete if missing core tags or lacking cover art
    is_incomplete = bool(missing_fields) or not has_cover_art

    return ScanResult(
        path=path,
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
        bits_per_sample=bits_per_sample,
        existing_tags=existing_tags,
        missing_fields=sorted(missing_fields),
        has_cover_art=has_cover_art,
        cover_art_info=cover_info,
        is_incomplete=is_incomplete,
    )


def scan_path(target_path: Path | str, recursive: bool = True) -> list[ScanResult]:
    """Scan a single file or a directory of FLAC files."""
    path = Path(target_path).resolve()
    results: list[ScanResult] = []

    if path.is_file():
        if path.suffix.lower() == ".flac":
            results.append(inspect_flac(path))
        return results

    if path.is_dir():
        pattern = "**/*.flac" if recursive else "*.flac"
        for flac_file in sorted(path.glob(pattern)):
            try:
                results.append(inspect_flac(flac_file))
            except Exception:
                # Log or continue on unreadable files during bulk directory scan
                continue

    return results
