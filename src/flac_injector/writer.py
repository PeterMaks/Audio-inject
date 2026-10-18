"""Mutagen FLAC and MP3 metadata and cover art injector with read-back verification."""

import io
from pathlib import Path
from typing import Any

from mutagen.flac import FLAC, FLACNoHeaderError, Picture
from mutagen.id3 import (
    APIC,
    ID3,
    TALB,
    TBPM,
    TCOM,
    TCON,
    TCOP,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TPUB,
    TRCK,
    TSRC,
    TXXX,
)
from mutagen.mp3 import MP3
from mutagen.mp3 import HeaderNotFoundError as MP3HeaderNotFoundError
from PIL import Image

from flac_injector.models import TrackMetadata


class InjectionError(Exception):
    """Raised when metadata or cover art injection fails."""


def inject_metadata(
    file_path: Path | str,
    metadata: TrackMetadata,
    cover_art_bytes: bytes | None = None,
    cover_art_mime: str | None = None,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    """Inject canonical metadata and cover art into a FLAC or MP3 audio file."""
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Target audio file not found: {path}")

    ext = path.suffix.lower()
    if ext == ".flac":
        return _inject_flac(
            path,
            metadata,
            cover_art_bytes,
            cover_art_mime,
            overwrite_existing,
        )
    elif ext == ".mp3":
        return _inject_mp3(
            path,
            metadata,
            cover_art_bytes,
            cover_art_mime,
            overwrite_existing,
        )
    elif ext in {".wav", ".wave", ".aiff", ".aif"}:
        raise InjectionError(
            f"Cannot inject tags directly into uncompressed audio '{path.name}'. "
            "Please convert to FLAC first using 'flac-meta-injector convert'."
        )
    else:
        # Default to FLAC injection for unknown extensions
        return _inject_flac(
            path,
            metadata,
            cover_art_bytes,
            cover_art_mime,
            overwrite_existing,
        )


def _inject_flac(
    path: Path,
    metadata: TrackMetadata,
    cover_art_bytes: bytes | None,
    cover_art_mime: str | None,
    overwrite_existing: bool,
) -> dict[str, Any]:
    """Inject Vorbis Comments and Picture block into a FLAC file."""
    try:
        audio = FLAC(str(path))
    except FLACNoHeaderError as e:
        raise InjectionError(f"File is not a valid FLAC audio file: {path}") from e
    except Exception as e:
        raise InjectionError(f"Failed to open FLAC file for writing: {path} ({e})") from e

    vorbis_dict = metadata.to_vorbis_comments()
    tags_injected: list[str] = []

    if audio.tags is None:
        audio.add_tags()

    for key, values in vorbis_dict.items():
        key_upper = key.upper()
        if not overwrite_existing and key_upper in audio and audio[key_upper]:
            continue
        audio[key_upper] = values
        tags_injected.append(key_upper)

    art_data = cover_art_bytes or metadata.cover_art_bytes
    art_injected = False
    art_info: dict[str, Any] = {}

    if art_data:
        try:
            with Image.open(io.BytesIO(art_data)) as img:
                width, height = img.size
                img_format = (img.format or "JPEG").upper()
                mime = (
                    cover_art_mime
                    or metadata.cover_art_mime
                    or f"image/{img_format.lower()}"
                )
                if mime == "image/jpg":
                    mime = "image/jpeg"

                mode_to_depth = {
                    "1": 1,
                    "L": 8,
                    "P": 8,
                    "RGB": 24,
                    "RGBA": 32,
                    "CMYK": 32,
                    "YCbCr": 24,
                }
                depth = mode_to_depth.get(img.mode, 24)

            pic = Picture()
            pic.type = 3  # Cover (front)
            pic.mime = mime
            pic.desc = "Front Cover"
            pic.width = width
            pic.height = height
            pic.depth = depth
            pic.data = art_data

            other_pics = [p for p in audio.pictures if getattr(p, "type", None) != 3]
            audio.clear_pictures()
            for p in other_pics:
                audio.add_picture(p)
            audio.add_picture(pic)
            art_injected = True
            art_info = {
                "mime": mime,
                "width": width,
                "height": height,
                "depth": depth,
                "bytes": len(art_data),
            }
        except Exception as e:
            raise InjectionError(f"Failed to process and embed cover art into {path}: {e}") from e

    try:
        audio.save()
    except Exception as e:
        raise InjectionError(f"Failed to save FLAC metadata to disk: {path} ({e})") from e

    # Immediate Read-Back Verification
    try:
        verify_audio = FLAC(str(path))
        verified_tags = (
            {k.upper(): v for k, v in verify_audio.tags.items()}
            if verify_audio.tags
            else {}
        )
        verified_has_cover = any(getattr(p, "type", None) == 3 for p in verify_audio.pictures)

        for tag in tags_injected:
            if tag not in verified_tags:
                raise InjectionError(f"Verification failed: Tag {tag} not found after write!")

        if art_injected and not verified_has_cover:
            raise InjectionError(
                "Verification failed: Cover art Picture block not found after write!"
            )

    except Exception as e:
        raise InjectionError(f"Post-injection readback verification failed for {path}: {e}") from e

    return {
        "path": str(path),
        "format": "flac",
        "tags_injected": tags_injected,
        "cover_art_injected": art_injected,
        "cover_art_info": art_info,
        "status": "success",
    }


def _inject_mp3(
    path: Path,
    metadata: TrackMetadata,
    cover_art_bytes: bytes | None,
    cover_art_mime: str | None,
    overwrite_existing: bool,
) -> dict[str, Any]:
    """Inject ID3v2.4 frames and APIC cover art into an MP3 file."""
    try:
        audio = MP3(str(path), ID3=ID3)
    except MP3HeaderNotFoundError as e:
        raise InjectionError(f"File is not a valid MP3 audio file: {path}") from e
    except Exception as e:
        raise InjectionError(f"Failed to open MP3 file for writing: {path} ({e})") from e

    if audio.tags is None:
        try:
            audio.add_tags()
        except Exception:
            audio.tags = ID3()

    tags = audio.tags
    id3_dict = metadata.to_id3_dict()
    tags_injected: list[str] = []

    def set_frame(frame_cls: Any, frame_id: str, value: Any) -> None:
        if value is None:
            return
        if not overwrite_existing and frame_id in tags:
            return
        if isinstance(value, list):
            tags.add(frame_cls(encoding=3, text=value))
        else:
            tags.add(frame_cls(encoding=3, text=[str(value)]))
        tags_injected.append(frame_id)

    set_frame(TIT2, "TIT2", id3_dict.get("TIT2"))
    set_frame(TPE1, "TPE1", id3_dict.get("TPE1"))
    set_frame(TALB, "TALB", id3_dict.get("TALB"))
    set_frame(TPE2, "TPE2", id3_dict.get("TPE2"))
    set_frame(TRCK, "TRCK", id3_dict.get("TRCK"))
    set_frame(TPOS, "TPOS", id3_dict.get("TPOS"))
    set_frame(TDRC, "TDRC", id3_dict.get("TDRC"))
    set_frame(TCON, "TCON", id3_dict.get("TCON"))
    set_frame(TSRC, "TSRC", id3_dict.get("TSRC"))
    set_frame(TBPM, "TBPM", id3_dict.get("TBPM"))
    set_frame(TCOP, "TCOP", id3_dict.get("TCOP"))
    set_frame(TCOM, "TCOM", id3_dict.get("TCOM"))
    set_frame(TPUB, "TPUB", id3_dict.get("TPUB"))

    # Add TXXX frames
    for desc, val in id3_dict.get("TXXX", {}).items():
        frame_id = f"TXXX:{desc}"
        if not overwrite_existing and frame_id in tags:
            continue
        tags.add(TXXX(encoding=3, desc=desc, text=[str(val)]))
        tags_injected.append(frame_id)

    # Inject APIC Front Cover
    art_data = cover_art_bytes or metadata.cover_art_bytes
    art_injected = False
    art_info: dict[str, Any] = {}

    if art_data:
        try:
            with Image.open(io.BytesIO(art_data)) as img:
                width, height = img.size
                img_format = (img.format or "JPEG").upper()
                mime = (
                    cover_art_mime
                    or metadata.cover_art_mime
                    or f"image/{img_format.lower()}"
                )
                if mime == "image/jpg":
                    mime = "image/jpeg"

            # Remove existing APIC cover frames
            apic_keys = [k for k in tags.keys() if k.startswith("APIC")]
            for k in apic_keys:
                del tags[k]

            tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # Cover front
                    desc="Front Cover",
                    data=art_data,
                )
            )
            art_injected = True
            art_info = {
                "mime": mime,
                "width": width,
                "height": height,
                "depth": 24,
                "bytes": len(art_data),
            }
        except Exception as e:
            raise InjectionError(f"Failed to embed APIC cover art into {path}: {e}") from e

    try:
        audio.save()
    except Exception as e:
        raise InjectionError(f"Failed to save MP3 ID3 tags to disk: {path} ({e})") from e

    # Read-back verification
    try:
        verify_audio = MP3(str(path), ID3=ID3)
        vtags = verify_audio.tags or {}
        for tag_id in ["TIT2", "TPE1", "TALB"]:
            if tag_id in tags_injected and tag_id not in vtags:
                raise InjectionError(
                    f"Verification failed: MP3 Frame {tag_id} missing after write!"
                )

        if art_injected:
            has_apic = any(k.startswith("APIC") for k in vtags.keys())
            if not has_apic:
                raise InjectionError(
                    "Verification failed: APIC cover art missing in MP3 after write!"
                )
    except Exception as e:
        raise InjectionError(
            f"Post-injection readback verification failed for MP3 {path}: {e}"
        ) from e

    return {
        "path": str(path),
        "format": "mp3",
        "tags_injected": tags_injected,
        "cover_art_injected": art_injected,
        "cover_art_info": art_info,
        "status": "success",
    }
