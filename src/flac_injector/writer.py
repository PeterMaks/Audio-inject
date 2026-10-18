"""Mutagen FLAC Vorbis Comment and Picture block injector with read-back verification."""

import io
from pathlib import Path
from typing import Any

from mutagen.flac import FLAC, FLACNoHeaderError, Picture
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
    """Inject canonical Vorbis Comments and Picture block into a FLAC file."""
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Target FLAC file not found: {path}")

    try:
        audio = FLAC(str(path))
    except FLACNoHeaderError as e:
        raise InjectionError(f"File is not a valid FLAC audio file: {path}") from e
    except Exception as e:
        raise InjectionError(f"Failed to open FLAC file for writing: {path} ({e})") from e

    # 1. Prepare Vorbis comments
    vorbis_dict = metadata.to_vorbis_comments()
    tags_injected: list[str] = []

    # Initialize audio.tags if completely missing
    if audio.tags is None:
        audio.add_tags()

    for key, values in vorbis_dict.items():
        key_upper = key.upper()
        # If not overwriting, do not replace existing non-empty tags
        if not overwrite_existing and key_upper in audio and audio[key_upper]:
            continue
        audio[key_upper] = values
        tags_injected.append(key_upper)

    # 2. Inject Picture block (Type 3: Cover front)
    art_data = cover_art_bytes or metadata.cover_art_bytes
    art_injected = False
    art_info: dict[str, Any] = {}

    if art_data:
        try:
            # Validate image integrity and dimensions using Pillow
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

            # Build Mutagen Picture object
            pic = Picture()
            pic.type = 3  # Cover (front)
            pic.mime = mime
            pic.desc = "Front Cover"
            pic.width = width
            pic.height = height
            pic.depth = depth
            pic.data = art_data

            # Clear existing front cover pictures (type 3) to prevent duplicates
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

    # 3. Save modified FLAC headers losslessly
    try:
        audio.save()
    except Exception as e:
        raise InjectionError(f"Failed to save FLAC metadata to disk: {path} ({e})") from e

    # 4. Immediate Read-Back Verification
    try:
        verify_audio = FLAC(str(path))
        verified_tags = (
            {k.upper(): v for k, v in verify_audio.tags.items()}
            if verify_audio.tags
            else {}
        )
        verified_has_cover = any(getattr(p, "type", None) == 3 for p in verify_audio.pictures)

        # Confirm all injected tags are present in verified readback
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
        "tags_injected": tags_injected,
        "cover_art_injected": art_injected,
        "cover_art_info": art_info,
        "status": "success",
    }
