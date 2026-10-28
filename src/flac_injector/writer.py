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
from mutagen.wave import WAVE
from PIL import Image

from flac_injector.models import PLACEHOLDER_TAG_VALUES, TrackMetadata, resolve_album_name


class InjectionError(Exception):
    """Raised when metadata or cover art injection fails."""


def inject_metadata(
    file_path: Path | str,
    metadata: TrackMetadata,
    cover_art_bytes: bytes | None = None,
    cover_art_mime: str | None = None,
    overwrite_existing: bool = False,
    overwrite_art: bool = False,
    overwrite_tags: list[str] | set[str] | None = None,
) -> dict[str, Any]:
    """Inject canonical metadata and cover art into a FLAC, MP3, or WAV audio file."""
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Target audio file not found: {path}")

    # Ensure canonical album resolution across all file formats
    metadata.album = resolve_album_name(
        album=metadata.album,
        title=metadata.title,
        total_tracks=metadata.track_total,
    )

    ext = path.suffix.lower()
    if ext == ".flac":
        return _inject_flac(
            path,
            metadata,
            cover_art_bytes,
            cover_art_mime,
            overwrite_existing,
            overwrite_art,
            overwrite_tags,
        )
    elif ext == ".mp3":
        return _inject_mp3(
            path,
            metadata,
            cover_art_bytes,
            cover_art_mime,
            overwrite_existing,
            overwrite_art,
            overwrite_tags,
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
            overwrite_art,
            overwrite_tags,
        )


def _inject_flac(
    path: Path,
    metadata: TrackMetadata,
    cover_art_bytes: bytes | None,
    cover_art_mime: str | None,
    overwrite_existing: bool,
    overwrite_art: bool = False,
    overwrite_tags: list[str] | set[str] | None = None,
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
    clean_overwrite_tags = {t.upper() for t in overwrite_tags} if overwrite_tags else set()

    if audio.tags is None:
        audio.add_tags()

    tag_aliases = {
        "ALBUMARTIST": ["ALBUM ARTIST", "ALBUM_ARTIST", "BAND"],
        "TRACKNUMBER": ["TRACK"],
        "TRACKTOTAL": ["TOTALTRACKS"],
        "DISCNUMBER": ["DISC"],
        "DISCTOTAL": ["TOTALDISCS"],
    }

    for key, values in vorbis_dict.items():
        key_upper = key.upper()
        force_ow = overwrite_existing or (key_upper in clean_overwrite_tags)
        if not force_ow and key_upper in audio and audio[key_upper]:
            existing_vals = audio[key_upper]
            # If all existing values are placeholders (e.g. "Unknown Album"), treat as gap to overwrite
            clean_existing = [
                str(v).strip()
                for v in existing_vals
                if str(v).strip() and str(v).strip().lower().strip("\"'") not in PLACEHOLDER_TAG_VALUES
            ]
            if clean_existing:
                # Deduplicate existing tag values if they contain duplicate entries
                seen_items: set[str] = set()
                deduped: list[str] = []
                for item in existing_vals:
                    s = str(item).strip()
                    if s.lower() not in seen_items:
                        seen_items.add(s.lower())
                        deduped.append(s)
                if len(deduped) != len(existing_vals):
                    audio[key_upper] = deduped
                continue

        audio[key_upper] = values
        tags_injected.append(key_upper)

        # Clean conflicting legacy alias tags to prevent repeating metadata in players
        for alias in tag_aliases.get(key_upper, []):
            if alias in audio:
                del audio[alias]

    art_data = cover_art_bytes or metadata.cover_art_bytes
    art_injected = False
    art_info: dict[str, Any] = {}

    # Guard existing valid cover art meeting COVER_ART_MIN_RESOLUTION
    if art_data and not overwrite_existing and not overwrite_art:
        from flac_injector.config import get_settings
        min_res = get_settings().cover_art_min_resolution
        has_valid_cover = any(
            getattr(p, "type", None) == 3
            and (getattr(p, "width", 0) or 0) >= min_res
            and (getattr(p, "height", 0) or 0) >= min_res
            for p in (audio.pictures or [])
        )
        if has_valid_cover:
            art_data = None

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

            # Clear all pictures before adding the new verified Picture block
            audio.clear_pictures()
            audio.add_picture(pic)
            art_injected = True

            # Clean legacy Vorbis comment picture tags that cause duplicate art display
            for legacy_pic in ("METADATA_BLOCK_PICTURE", "COVERART", "COVERARTMIME"):
                if legacy_pic in audio:
                    del audio[legacy_pic]
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


def _apply_id3_tags(
    tags: Any,
    metadata: TrackMetadata,
    path: Path,
    cover_art_bytes: bytes | None,
    cover_art_mime: str | None,
    overwrite_existing: bool,
    overwrite_art: bool,
    overwrite_tags: list[str] | set[str] | None = None,
) -> tuple[list[str], bool, dict[str, Any]]:
    """Apply TrackMetadata frames and APIC cover art to an ID3 container."""
    id3_dict = metadata.to_id3_dict()
    tags_injected: list[str] = []
    clean_overwrite_tags = {t.upper() for t in overwrite_tags} if overwrite_tags else set()

    frame_to_canonical = {
        "TIT2": "TITLE",
        "TPE1": "ARTIST",
        "TALB": "ALBUM",
        "TPE2": "ALBUMARTIST",
        "TRCK": "TRACKNUMBER",
        "TPOS": "DISCNUMBER",
        "TDRC": "DATE",
        "TCON": "GENRE",
        "TSRC": "ISRC",
        "TBPM": "BPM",
        "TCOP": "COPYRIGHT",
        "TCOM": "COMPOSER",
        "TPUB": "LABEL",
    }

    def set_frame(frame_cls: Any, frame_id: str, value: Any) -> None:
        if value is None:
            return
        canonical = frame_to_canonical.get(frame_id, frame_id)
        force_ow = (
            overwrite_existing
            or (frame_id in clean_overwrite_tags)
            or (canonical in clean_overwrite_tags)
        )
        if not force_ow and frame_id in tags:
            # Check if current frame value is a placeholder
            curr_text = getattr(tags[frame_id], "text", [])
            clean_curr = [
                str(t).strip()
                for t in curr_text
                if str(t).strip() and str(t).strip().lower().strip("\"'") not in PLACEHOLDER_TAG_VALUES
            ]
            if clean_curr:
                return  # Genuine frame value exists; preserve it
        if isinstance(value, list):
            seen_items: set[str] = set()
            dedup_val: list[str] = []
            for item in value:
                s = str(item).strip()
                if s.lower() not in seen_items:
                    seen_items.add(s.lower())
                    dedup_val.append(s)
            tags.add(frame_cls(encoding=3, text=dedup_val))
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
        force_ow = (
            overwrite_existing
            or (frame_id in clean_overwrite_tags)
            or ("TXXX" in clean_overwrite_tags)
        )
        if not force_ow and frame_id in tags:
            continue
        tags.add(TXXX(encoding=3, desc=desc, text=[str(val)]))
        tags_injected.append(frame_id)

    # Inject APIC Front Cover
    art_data = cover_art_bytes or metadata.cover_art_bytes
    art_injected = False
    art_info: dict[str, Any] = {}

    # Guard existing valid cover art meeting COVER_ART_MIN_RESOLUTION
    if art_data and not overwrite_existing and not overwrite_art:
        from flac_injector.config import get_settings
        min_res = get_settings().cover_art_min_resolution
        apic_frames = tags.getall("APIC") if hasattr(tags, "getall") else []
        has_valid_cover = False
        for apic in apic_frames:
            if getattr(apic, "type", 3) == 3:
                try:
                    with Image.open(io.BytesIO(apic.data)) as img:
                        w, h = img.size
                        if w >= min_res and h >= min_res:
                            has_valid_cover = True
                            break
                except Exception:
                    pass
        if has_valid_cover:
            art_data = None

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

            # Remove existing APIC cover frames cleanly
            try:
                tags.delall("APIC")
            except Exception:
                pass
            apic_keys = [k for k in list(tags.keys()) if k.startswith("APIC")]
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

    return tags_injected, art_injected, art_info


def _inject_mp3(
    path: Path,
    metadata: TrackMetadata,
    cover_art_bytes: bytes | None,
    cover_art_mime: str | None,
    overwrite_existing: bool,
    overwrite_art: bool = False,
    overwrite_tags: list[str] | set[str] | None = None,
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

    tags_injected, art_injected, art_info = _apply_id3_tags(
        audio.tags,
        metadata,
        path,
        cover_art_bytes,
        cover_art_mime,
        overwrite_existing,
        overwrite_art,
        overwrite_tags,
    )

    try:
        audio.save(v2_version=4)
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


def _inject_wav(
    path: Path,
    metadata: TrackMetadata,
    cover_art_bytes: bytes | None,
    cover_art_mime: str | None,
    overwrite_existing: bool,
    overwrite_art: bool = False,
) -> dict[str, Any]:
    """Inject ID3v2.4 frames and APIC cover art into a WAV file."""
    try:
        audio = WAVE(str(path))
    except Exception as e:
        raise InjectionError(f"File is not a valid WAV audio file: {path}") from e

    if audio.tags is None:
        try:
            audio.add_tags()
        except Exception:
            pass

    if audio.tags is None:
        raise InjectionError(f"Failed to initialize ID3 tags for WAV file: {path}")

    tags_injected, art_injected, art_info = _apply_id3_tags(
        audio.tags,
        metadata,
        path,
        cover_art_bytes,
        cover_art_mime,
        overwrite_existing,
        overwrite_art,
    )

    try:
        audio.save(v2_version=4)
    except Exception as e:
        raise InjectionError(f"Failed to save WAV ID3 tags to disk: {path} ({e})") from e

    # Read-back verification
    try:
        verify_audio = WAVE(str(path))
        vtags = verify_audio.tags or {}
        for tag_id in ["TIT2", "TPE1", "TALB"]:
            if tag_id in tags_injected and tag_id not in vtags:
                raise InjectionError(
                    f"Verification failed: WAV Frame {tag_id} missing after write!"
                )
    except Exception as e:
        raise InjectionError(
            f"Post-injection readback verification failed for WAV {path}: {e}"
        ) from e

    return {
        "path": str(path),
        "format": "wav",
        "tags_injected": tags_injected,
        "cover_art_injected": art_injected,
        "cover_art_info": art_info,
        "status": "success",
    }


def clean_embedded_art(file_path: Path | str, dry_run: bool = False) -> dict[str, Any]:
    """Deduplicate embedded picture blocks and remove legacy picture tags from an audio file."""
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Target audio file not found: {path}")

    ext = path.suffix.lower()
    if ext == ".flac":
        try:
            audio = FLAC(str(path))
        except Exception as e:
            raise InjectionError(f"Cannot open FLAC file {path}: {e}") from e

        pics_before = len(audio.pictures) if audio.pictures else 0
        legacy_removed = []
        modified = False

        # Clean legacy Vorbis comment picture tags
        if audio.tags:
            for tag in ["METADATA_BLOCK_PICTURE", "COVERART", "COVERARTMIME"]:
                if tag in audio:
                    legacy_removed.append(tag)
                    if not dry_run:
                        del audio[tag]
                    modified = True

        # Deduplicate picture blocks
        if pics_before > 1:
            # Pick the best front cover (type 3), or largest resolution/byte size
            front_pics = [p for p in audio.pictures if getattr(p, "type", None) == 3]
            best_pic = front_pics[0] if front_pics else audio.pictures[0]
            # If multiple front pictures, pick the one with largest data
            if front_pics:
                best_pic = max(front_pics, key=lambda p: len(getattr(p, "data", b"")))

            if not dry_run:
                audio.clear_pictures()
                audio.add_picture(best_pic)
            modified = True

        if modified and not dry_run:
            audio.save()

        pics_after = 1 if pics_before > 0 else 0
        return {
            "path": str(path),
            "format": "flac",
            "pictures_before": pics_before,
            "pictures_after": pics_after if pics_before > 1 else pics_before,
            "legacy_tags_removed": legacy_removed,
            "modified": modified,
        }

    elif ext in {".mp3", ".wav", ".wave"}:
        try:
            if ext == ".mp3":
                audio = MP3(str(path), ID3=ID3)
            else:
                audio = WAVE(str(path))
        except Exception as e:
            raise InjectionError(f"Cannot open {ext.upper()} file {path}: {e}") from e

        tags = audio.tags or {}
        apic_keys = [k for k in tags.keys() if k.startswith("APIC")]
        pics_before = len(apic_keys)
        modified = False

        if pics_before > 1:
            # Keep the primary front cover (type 3), or the first APIC frame
            front_apics = [tags[k] for k in apic_keys if getattr(tags[k], "type", None) == 3]
            best_apic = front_apics[0] if front_apics else tags[apic_keys[0]]

            if not dry_run:
                for k in apic_keys:
                    del tags[k]
                tags.add(best_apic)
                audio.save(v2_version=4)
            modified = True

        return {
            "path": str(path),
            "format": ext.lstrip("."),
            "pictures_before": pics_before,
            "pictures_after": 1 if pics_before > 1 else pics_before,
            "legacy_tags_removed": [],
            "modified": modified,
        }

    return {
        "path": str(path),
        "format": ext.lstrip("."),
        "pictures_before": 0,
        "pictures_after": 0,
        "legacy_tags_removed": [],
        "modified": False,
    }
