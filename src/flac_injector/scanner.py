"""Audio file inspection and missing-tag detection for FLAC, MP3, and WAV files."""

import io
from pathlib import Path
from typing import Any

from mutagen.flac import FLAC, FLACNoHeaderError
from mutagen.mp3 import MP3
from mutagen.mp3 import HeaderNotFoundError as MP3HeaderNotFoundError
from mutagen.wave import WAVE
from PIL import Image

from flac_injector.models import ScanResult

# Tags considered essential for a complete music collection
CORE_TAGS = {"TITLE", "ARTIST", "ALBUM"}
RECOMMENDED_TAGS = {"TRACKNUMBER", "DATE", "GENRE"}
SUPPORTED_EXTENSIONS = {".flac", ".mp3", ".wav", ".wave", ".aiff", ".aif"}


class AudioScannerError(Exception):
    """Raised when an error occurs while scanning an audio file."""


FLACScannerError = AudioScannerError  # Backward-compatibility alias


def inspect_audio(file_path: Path | str) -> ScanResult:
    """Inspect an audio file (FLAC, MP3, WAV) and return metadata completeness status."""
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()
    if ext == ".flac":
        return _inspect_flac(path)
    elif ext == ".mp3":
        return _inspect_mp3(path)
    elif ext in {".wav", ".wave", ".aiff", ".aif"}:
        return _inspect_wav(path)
    else:
        # Fall back to FLAC inspection if unknown extension
        return _inspect_flac(path)


def inspect_flac(file_path: Path | str) -> ScanResult:
    """Inspect a single FLAC file. Kept for backward compatibility."""
    return inspect_audio(file_path)


def _inspect_flac(path: Path) -> ScanResult:
    """Inspect a FLAC file using Mutagen."""
    try:
        audio = FLAC(str(path))
    except FLACNoHeaderError as e:
        raise AudioScannerError(f"Not a valid FLAC file: {path} ({e})") from e
    except Exception as e:
        raise AudioScannerError(f"Failed to read FLAC metadata from {path}: {e}") from e

    info = audio.info
    duration = float(getattr(info, "length", 0.0))
    sample_rate = int(getattr(info, "sample_rate", 0))
    channels = int(getattr(info, "channels", 0))
    bits_per_sample = int(getattr(info, "bits_per_sample", 0))

    existing_tags: dict[str, list[str]] = {}
    if audio.tags:
        for k, v in audio.tags.items():
            existing_tags[k.upper()] = [str(item).strip() for item in v if str(item).strip()]

    missing_fields = _detect_missing_fields(existing_tags)

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

    is_incomplete = any(tag in missing_fields for tag in CORE_TAGS) or not has_cover_art

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
        audio_format="flac",
    )


def _inspect_mp3(path: Path) -> ScanResult:
    """Inspect an MP3 file using Mutagen and ID3 tags."""
    try:
        audio = MP3(str(path))
    except MP3HeaderNotFoundError as e:
        raise AudioScannerError(f"Not a valid MP3 file: {path} ({e})") from e
    except Exception as e:
        raise AudioScannerError(f"Failed to read MP3 metadata from {path}: {e}") from e

    info = audio.info
    duration = float(getattr(info, "length", 0.0))
    sample_rate = int(getattr(info, "sample_rate", 0))
    channels = int(getattr(info, "channels", 0))
    bits_per_sample = 16  # MP3 decoded PCM standard

    existing_tags: dict[str, list[str]] = {}
    has_cover_art = False
    cover_info: dict[str, Any] | None = None

    if audio.tags:
        # Standard ID3 to Canonical Tag mapping
        id3_map = {
            "TIT2": "TITLE",
            "TPE1": "ARTIST",
            "TALB": "ALBUM",
            "TPE2": "ALBUMARTIST",
            "TRCK": "TRACKNUMBER",
            "TPOS": "DISCNUMBER",
            "TDRC": "DATE",
            "TYER": "DATE",
            "TCON": "GENRE",
            "TSRC": "ISRC",
            "TBPM": "BPM",
            "TCOP": "COPYRIGHT",
            "TCOM": "COMPOSER",
            "TPUB": "LABEL",
        }

        for frame_key, frame_obj in audio.tags.items():
            # Check APIC frames for cover art
            if frame_key.startswith("APIC"):
                data = getattr(frame_obj, "data", b"")
                mime = getattr(frame_obj, "mime", "image/jpeg")
                width, height = 0, 0
                if data:
                    try:
                        with Image.open(io.BytesIO(data)) as img:
                            width, height = img.size
                    except Exception:
                        pass
                has_cover_art = True
                cover_info = {
                    "type": getattr(frame_obj, "type", 3),
                    "mime": mime,
                    "width": width,
                    "height": height,
                    "depth": 24,
                    "size_bytes": len(data),
                }
                continue

            # Check TXXX frames for MusicBrainz / AcoustID tags
            if frame_key.startswith("TXXX"):
                desc = getattr(frame_obj, "desc", "").lower()
                text = getattr(frame_obj, "text", [])
                val = str(text[0]).strip() if text else ""
                if val:
                    if "track id" in desc:
                        existing_tags["MUSICBRAINZ_TRACKID"] = [val]
                    elif "album id" in desc:
                        existing_tags["MUSICBRAINZ_ALBUMID"] = [val]
                    elif "artist id" in desc:
                        existing_tags["MUSICBRAINZ_ARTISTID"] = [val]
                    elif "acoustid" in desc:
                        existing_tags["ACOUSTID_ID"] = [val]
                continue

            # Standard text frames
            prefix = frame_key[:4]
            if prefix in id3_map:
                canonical_name = id3_map[prefix]
                text_vals = getattr(frame_obj, "text", [])
                if isinstance(text_vals, list):
                    vals = [str(t).strip() for t in text_vals if str(t).strip()]
                else:
                    vals = [str(text_vals).strip()] if str(text_vals).strip() else []
                if vals:
                    # Clean TRCK like "1/14" -> tracknumber "1"
                    if canonical_name == "TRACKNUMBER" and "/" in vals[0]:
                        parts = vals[0].split("/", 1)
                        existing_tags["TRACKNUMBER"] = [parts[0].strip()]
                        existing_tags["TRACKTOTAL"] = [parts[1].strip()]
                    else:
                        existing_tags[canonical_name] = vals

    missing_fields = _detect_missing_fields(existing_tags)
    is_incomplete = any(tag in missing_fields for tag in CORE_TAGS) or not has_cover_art

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
        audio_format="mp3",
    )


def _inspect_wav(path: Path) -> ScanResult:
    """Inspect a WAV audio file."""
    try:
        audio = WAVE(str(path))
    except Exception as e:
        raise AudioScannerError(f"Failed to read WAV audio header from {path}: {e}") from e

    info = audio.info
    duration = float(getattr(info, "length", 0.0))
    sample_rate = int(getattr(info, "sample_rate", 0))
    channels = int(getattr(info, "channels", 0))
    bits_per_sample = int(getattr(info, "bits_per_sample", 16))

    existing_tags: dict[str, list[str]] = {}
    if audio.tags:
        for k, v in audio.tags.items():
            existing_tags[k.upper()] = [str(item).strip() for item in v if str(item).strip()]

    missing_fields = _detect_missing_fields(existing_tags)
    # WAV files lack standard high-res embedded front cover blocks and need conversion to FLAC
    is_incomplete = True

    return ScanResult(
        path=path,
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
        bits_per_sample=bits_per_sample,
        existing_tags=existing_tags,
        missing_fields=sorted(missing_fields),
        has_cover_art=False,
        cover_art_info=None,
        is_incomplete=is_incomplete,
        audio_format="wav",
    )


PLACEHOLDER_TAG_VALUES = {
    "unknown",
    "unknown album",
    "unknown artist",
    "unknown title",
    "untitled",
    "none",
    "null",
    "no album",
    "no artist",
    "placeholder",
}


def _detect_missing_fields(existing_tags: dict[str, list[str]]) -> list[str]:
    """Identify which core and recommended tags are missing or set to unknown placeholders."""
    missing: list[str] = []
    for tag in CORE_TAGS | RECOMMENDED_TAGS:
        if tag not in existing_tags or not existing_tags[tag]:
            if tag == "DATE" and "YEAR" in existing_tags and existing_tags["YEAR"]:
                continue
            missing.append(tag)
        else:
            # Check if all values for this tag are empty or placeholder values (e.g. "Unknown Album")
            clean_vals = [
                str(v).strip()
                for v in existing_tags[tag]
                if str(v).strip() and str(v).strip().lower() not in PLACEHOLDER_TAG_VALUES
            ]
            if not clean_vals:
                missing.append(tag)
    return missing


def scan_path(target_path: Path | str, recursive: bool = True) -> list[ScanResult]:
    """Scan a single file or a directory of audio files (FLAC, MP3, WAV)."""
    path = Path(target_path).resolve()
    results: list[ScanResult] = []

    if path.is_file():
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            results.append(inspect_audio(path))
        return results

    if path.is_dir():
        pattern = "**/*" if recursive else "*"
        for candidate in sorted(path.glob(pattern)):
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    results.append(inspect_audio(candidate))
                except Exception:
                    continue

    return results
