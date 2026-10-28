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


def run_scan_command(
    paths: list[str],
    recursive: bool = True,
    only_incomplete: bool = False,
) -> dict[str, Any]:
    """Execute scan across a list of paths."""
    all_results: list[dict[str, Any]] = []
    seen: set[str] = set()

    for p_str in paths:
        target = Path(p_str)
        if not target.exists():
            continue
        scanned = scan_path(target, recursive=recursive)
        for s in scanned:
            norm_path = str(s.path)
            if norm_path not in seen:
                seen.add(norm_path)
                if only_incomplete and not s.is_incomplete:
                    continue
                all_results.append(serialize_scan_result(s))

    incomplete_count = sum(1 for r in all_results if r["is_incomplete"])
    format_counts: dict[str, int] = {}
    for r in all_results:
        fmt = r["audio_format"].upper()
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    return {
        "items": all_results,
        "total": len(all_results),
        "incomplete": incomplete_count,
        "complete": len(all_results) - incomplete_count,
        "format_counts": format_counts,
    }


def extract_embedded_art_data_url(file_path: Path) -> str | None:
    """Extract embedded front cover art and encode as a data URL."""
    ext = file_path.suffix.lower()
    try:
        if ext == ".flac":
            audio = FLAC(str(file_path))
            if audio.pictures:
                front_pictures = [p for p in audio.pictures if getattr(p, "type", None) == 3]
                target_pic = front_pictures[0] if front_pictures else audio.pictures[0]
                data = getattr(target_pic, "data", b"")
                mime = getattr(target_pic, "mime", "image/jpeg")
                if data:
                    b64 = base64.b64encode(data).decode("ascii")
                    return f"data:{mime};base64,{b64}"
        elif ext == ".mp3":
            audio = MP3(str(file_path))
            if audio.tags:
                for frame_key, frame_obj in audio.tags.items():
                    if frame_key.startswith("APIC"):
                        data = getattr(frame_obj, "data", b"")
                        mime = getattr(frame_obj, "mime", "image/jpeg")
                        if data:
                            b64 = base64.b64encode(data).decode("ascii")
                            return f"data:{mime};base64,{b64}"
    except Exception:
        pass
    return None


def run_inspect_command(path_str: str, include_art_base64: bool = True) -> dict[str, Any]:
    """Inspect detailed tags, properties, and cover art blocks of an audio file."""
    path = Path(path_str).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    res = inspect_audio(path)
    data = serialize_scan_result(res)

    if include_art_base64 and res.has_cover_art:
        data_url = extract_embedded_art_data_url(path)
        if data_url:
            data["cover_art_data_url"] = data_url

    return data


def run_fingerprint_command(path_str: str) -> dict[str, Any]:
    """Generate Chromaprint fingerprint and parse filename heuristics."""
    path = Path(path_str).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    fp = generate_fingerprint(path)
    hints = parse_filename_metadata(path)

    return {
        "path": str(path),
        "filename": path.name,
        "fingerprint": fp.fingerprint,
        "duration": fp.duration,
        "hints": hints,
    }


def serialize_track_metadata(meta: TrackMetadata) -> dict[str, Any]:
    """Convert TrackMetadata to a JSON dictionary."""
    data = meta.model_dump(exclude={"cover_art_bytes"})
    data["vorbis_comments"] = meta.to_vorbis_comments()
    data["id3_frames"] = meta.to_id3_dict()
    return data


async def run_inject_command(
    paths: list[str],
    threshold: float = 0.70,
    dry_run: bool = False,
    overwrite: bool = False,
    convert_wav: bool = True,
    recursive: bool = True,
    song_link: str | None = None,
) -> dict[str, Any]:
    """Resolve and inject metadata across multiple audio tracks with live progress."""
    settings = get_settings()
    allowed_exts = {".flac", ".mp3"}
    if convert_wav:
        allowed_exts.update({".wav", ".wave", ".aiff", ".aif"})

    target_files: list[Path] = []
    for p_str in paths:
        target = Path(p_str).resolve()
        if not target.exists():
            continue
        if target.is_file() and target.suffix.lower() in allowed_exts:
            target_files.append(target)
        elif target.is_dir():
            pattern = "**/*" if recursive else "*"
            for candidate in sorted(target.glob(pattern)):
                if candidate.is_file() and candidate.suffix.lower() in allowed_exts:
                    target_files.append(candidate)

    # Deduplicate while preserving order
    seen_files: set[str] = set()
    audio_files: list[Path] = []
    for f in target_files:
        norm = str(f)
        if norm not in seen_files:
            seen_files.add(norm)
            audio_files.append(f)

    total_files = len(audio_files)
    if total_files == 0:
        return {
            "processed": 0,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "items": [],
        }

    providers = [
        MusicBrainzProvider(settings=settings),
        AppleITunesProvider(settings=settings),
        DeezerProvider(settings=settings),
        SpotifyProvider(settings=settings),
        DiscogsProvider(settings=settings),
        SonglinkProvider(settings=settings),
    ]

    art_cache = ArtworkCache()
    items_result: list[dict[str, Any]] = []
    success_count = 0
    skipped_count = 0
    failed_count = 0

    try:
        for idx, file_path in enumerate(audio_files):
            file_percent = (idx / total_files) * 100.0
            emit_progress(
                stage="start",
                file=str(file_path),
                percent=file_percent,
                message=f"Scanning track {idx + 1}/{total_files}...",
                extra={"cover_art_url": None},
            )

            try:
                scan_res = inspect_audio(file_path)

                # WAV Conversion
                if scan_res.audio_format in ("wav", "wave", "aiff", "aif"):
                    if not convert_wav:
                        emit_progress(
                            stage="skip",
                            file=str(file_path),
                            percent=file_percent,
                            message="Skipping uncompressed WAV file (convert_wav disabled)",
                        )
                        skipped_count += 1
                        items_result.append({
                            "file": str(file_path),
                            "status": "skipped",
                            "reason": "WAV conversion disabled",
                        })
                        continue

                    if dry_run:
                        emit_progress(
                            stage="dry_run",
                            file=str(file_path),
                            percent=file_percent,
                            message=f"[DRY-RUN] Would convert {file_path.name} to FLAC",
                        )
                    else:
                        emit_progress(
                            stage="convert",
                            file=str(file_path),
                            percent=file_percent,
                            message=f"Converting WAV to FLAC: {file_path.name}...",
                        )
                        file_path = convert_to_flac(file_path)
                        scan_res = inspect_audio(file_path)

                if not scan_res.is_incomplete and not overwrite:
                    emit_progress(
                        stage="skip",
                        file=str(file_path),
                        percent=((idx + 1) / total_files) * 100.0,
                        message=f"Skipping already complete track: {file_path.name}",
                    )
                    skipped_count += 1
                    items_result.append({
                        "file": str(file_path),
                        "status": "skipped",
                        "reason": "Track already complete",
                    })
                    continue

                # Stage 1: Fingerprint
                emit_progress(
                    stage="fingerprint",
                    file=str(file_path),
                    percent=file_percent + (100.0 / total_files) * 0.15,
                    message=f"Generating Chromaprint acoustic fingerprint for {file_path.name}...",
                )
                fp = None
                try:
                    fp = generate_fingerprint(file_path)
                except Exception:
                    pass

                hints = parse_filename_metadata(file_path)
                if scan_res.existing_tags.get("TITLE"):
                    hints["title"] = scan_res.existing_tags["TITLE"][0]
                if scan_res.existing_tags.get("ARTIST"):
                    hints["artist"] = scan_res.existing_tags["ARTIST"][0]
                if scan_res.existing_tags.get("ALBUM"):
                    hints["album"] = scan_res.existing_tags["ALBUM"][0]

                all_candidates: list[TrackMetadata] = []
                mb_provider = next(
                    (p for p in providers if getattr(p, "name", "") == "musicbrainz"), None
                )
                apple_provider = next(
                    (p for p in providers if getattr(p, "name", "") == "apple_itunes"), None
                )
                deezer_provider = next(
                    (p for p in providers if getattr(p, "name", "") == "deezer"), None
                )
                spotify_provider = next(
                    (p for p in providers if getattr(p, "name", "") == "spotify"), None
                )
                discogs_provider = next(
                    (p for p in providers if getattr(p, "name", "") == "discogs"), None
                )
                songlink_provider = next(
                    (p for p in providers if getattr(p, "name", "") == "songlink"), None
                )

                # Stage 1.5: Direct Song Link / Streaming URL lookup
                direct_url = song_link
                if not direct_url:
                    for tag_key in ("SONGLINK", "URL", "WWWAUDIOFILE", "COMMENT", "DESCRIPTION"):
                        for val in scan_res.existing_tags.get(tag_key, []):
                            val_s = val.strip()
                            if any(
                                domain in val_s
                                for domain in (
                                    "song.link",
                                    "odesli.co",
                                    "open.spotify.com",
                                    "music.apple.com",
                                    "deezer.com",
                                    "youtube.com",
                                    "youtu.be",
                                    "tidal.com",
                                )
                            ):
                                direct_url = val_s
                                break
                        if direct_url:
                            break

                if direct_url and songlink_provider:
                    emit_progress(
                        stage="songlink",
                        file=str(file_path),
                        percent=file_percent + (100.0 / total_files) * 0.20,
                        message=f"Resolving via Songlink: {direct_url[:50]}...",
                    )
                    try:
                        sl_candidates = await songlink_provider.lookup_by_url(direct_url)
                        all_candidates.extend(sl_candidates)
                    except Exception as e:
                        emit_event({
                            "type": "provider_warning",
                            "provider": "songlink",
                            "message": str(e),
                        })

                # Stage 2: AcoustID & MusicBrainz
                emit_progress(
                    stage="acoustid",
                    file=str(file_path),
                    percent=file_percent + (100.0 / total_files) * 0.30,
                    message="Querying MusicBrainz & AcoustID...",
                )
                if fp and fp.fingerprint and mb_provider:
                    try:
                        mb_candidates = await mb_provider.lookup_by_fingerprint(
                            fp.fingerprint, fp.duration
                        )
                        all_candidates.extend(mb_candidates)
                    except Exception as e:
                        emit_event({
                            "type": "provider_warning",
                            "provider": "musicbrainz",
                            "message": str(e),
                        })

                # Stage 3: ISRC or Query search across providers
                isrc = next((c.isrc for c in all_candidates if c.isrc), None)
                if isrc:
                    emit_progress(
                        stage="itunes",
                        file=str(file_path),
                        percent=file_percent + (100.0 / total_files) * 0.45,
                        message=f"Querying Apple iTunes & providers by ISRC: {isrc}...",
                    )
                    tasks = []
                    if apple_provider:
                        tasks.append(apple_provider.lookup_by_isrc(isrc))
                    if deezer_provider:
                        tasks.append(deezer_provider.lookup_by_isrc(isrc))
                    if spotify_provider:
                        tasks.append(spotify_provider.lookup_by_isrc(isrc))
                    if discogs_provider:
                        tasks.append(discogs_provider.lookup_by_isrc(isrc))
                    if songlink_provider:
                        tasks.append(songlink_provider.lookup_by_isrc(isrc))
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for r in results:
                            if isinstance(r, list):
                                all_candidates.extend(r)
                elif hints.get("title"):
                    emit_progress(
                        stage="itunes",
                        file=str(file_path),
                        percent=file_percent + (100.0 / total_files) * 0.45,
                        message=f"Querying Apple iTunes & providers for: {hints.get('title')}...",
                    )
                    title = hints["title"]
                    artist = hints.get("artist")
                    album = hints.get("album")
                    tasks = []
                    if apple_provider:
                        tasks.append(apple_provider.lookup_by_query(title, artist))
                    if deezer_provider:
                        tasks.append(deezer_provider.lookup_by_query(title, artist))
                    if spotify_provider:
                        tasks.append(spotify_provider.lookup_by_query(title, artist))
                    if mb_provider:
                        tasks.append(mb_provider.lookup_by_query(title, artist, album))
                    if discogs_provider:
                        tasks.append(discogs_provider.lookup_by_query(title, artist, album))
                    if songlink_provider:
                        tasks.append(songlink_provider.lookup_by_query(title, artist, album))
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for r in results:
                            if isinstance(r, list):
                                all_candidates.extend(r)

                # Stage 4: Waterfall Aggregation
                emit_progress(
                    stage="merge",
                    file=str(file_path),
                    percent=file_percent + (100.0 / total_files) * 0.65,
                    message="Aggregating provider candidates with RapidFuzz scoring...",
                )
                best = aggregate_candidates(
                    all_candidates,
                    scan_res.duration_seconds,
                    hints,
                    confidence_threshold=threshold,
                )

                if not best:
                    failed_count += 1
                    items_result.append({
                        "file": str(file_path),
                        "status": "unmatched",
                        "reason": f"No match met confidence threshold ({threshold:.2f})",
                    })
                    emit_progress(
                        stage="unmatched",
                        file=str(file_path),
                        percent=((idx + 1) / total_files) * 100.0,
                        message=f"No confident match for {file_path.name}",
                    )
                    continue

                # Stage 5: Cover Art Fetch
                art_bytes = None
                art_mime = None
                if best.cover_art_url and (not scan_res.has_cover_art or overwrite):
                    emit_progress(
                        stage="art",
                        file=str(file_path),
                        percent=file_percent + (100.0 / total_files) * 0.80,
                        message="Fetching 3000x3000px master album artwork...",
                        extra={"cover_art_url": best.cover_art_url},
                    )
                    cached = art_cache.get(
                        best.artist,
                        best.album,
                        best.isrc or best.musicbrainz_albumid,
                    )
                    if cached:
                        art_bytes, art_mime = cached
                    else:
                        for p in providers:
                            art_result = await p.fetch_cover_art(best.cover_art_url)
                            if art_result:
                                art_bytes, art_mime = art_result
                                art_cache.set(
                                    best.artist,
                                    best.album,
                                    art_bytes,
                                    art_mime,
                                    best.isrc or best.musicbrainz_albumid,
                                )
                                break

                # Stage 6: Inject
                if dry_run:
                    emit_progress(
                        stage="dry_run",
                        file=str(file_path),
                        percent=((idx + 1) / total_files) * 100.0,
                        message=f"[DRY-RUN] Would inject {best.artist} - {best.title}",
                    )
                    items_result.append({
                        "file": str(file_path),
                        "status": "dry_run",
                        "metadata": serialize_track_metadata(best),
                        "cover_art_url": best.cover_art_url,
                        "confidence_score": best.confidence_score,
                    })
                    success_count += 1
                else:
                    emit_progress(
                        stage="write",
                        file=str(file_path),
                        percent=file_percent + (100.0 / total_files) * 0.95,
                        message=f"Writing lossless tags to {file_path.name}...",
                    )
                    inject_metadata(
                        file_path,
                        best,
                        cover_art_bytes=art_bytes,
                        cover_art_mime=art_mime,
                        overwrite_existing=overwrite,
                    )
                    success_count += 1
                    items_result.append({
                        "file": str(file_path),
                        "status": "injected",
                        "metadata": serialize_track_metadata(best),
                        "cover_art_url": best.cover_art_url,
                        "confidence_score": best.confidence_score,
                    })
                    emit_progress(
                        stage="done",
                        file=str(file_path),
                        percent=((idx + 1) / total_files) * 100.0,
                        message=f"Successfully injected: {best.artist} - {best.title}",
                    )
            except Exception as e:
                failed_count += 1
                items_result.append({
                    "file": str(file_path),
                    "status": "error",
                    "error": str(e),
                })
                emit_error(f"Error processing {file_path.name}: {e}", file=str(file_path))
    finally:
        for p in providers:
            await p.close()

    emit_progress(
        stage="finished",
        file="",
        percent=100.0,
        message=(
            f"Injection complete: {success_count} succeeded, "
            f"{failed_count} failed, {skipped_count} skipped."
        ),
    )

    return {
        "processed": total_files,
        "success": success_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "items": items_result,
    }


async def run_match_spotify_command(
    paths: list[str],
    data_path: str,
    threshold: float = 0.70,
    dry_run: bool = False,
    overwrite: bool = False,
    overwrite_art: bool = False,
    fetch_art: bool = False,
    convert_wav: bool = True,
    recursive: bool = True,
) -> dict[str, Any]:
    """Match audio files against a Spotify CSV or JSON export and fill metadata gaps."""
    spotify_file = Path(data_path).resolve()
    if not spotify_file.exists():
        raise FileNotFoundError(f"Spotify data file not found: {data_path}")

    spotify_records = load_spotify_data(spotify_file)
    if not spotify_records:
        return {
            "processed": 0,
            "matched": 0,
            "skipped": 0,
            "failed": 0,
            "records_loaded": 0,
            "items": [],
        }

    allowed_exts = {".flac", ".mp3"}
    if convert_wav:
        allowed_exts.update({".wav", ".wave", ".aiff", ".aif"})

    target_files: list[Path] = []
    for p_str in paths:
        target = Path(p_str).resolve()
        if not target.exists():
            continue
        if target.is_file() and target.suffix.lower() in allowed_exts:
            target_files.append(target)
        elif target.is_dir():
            pattern = "**/*" if recursive else "*"
            for candidate in sorted(target.glob(pattern)):
                if candidate.is_file() and candidate.suffix.lower() in allowed_exts:
                    target_files.append(candidate)

    seen_files: set[str] = set()
    audio_files: list[Path] = []
    for f in target_files:
        norm = str(f)
        if norm not in seen_files:
            seen_files.add(norm)
            audio_files.append(f)

    total_files = len(audio_files)
    if total_files == 0:
        return {
            "processed": 0,
            "matched": 0,
            "skipped": 0,
            "failed": 0,
            "records_loaded": len(spotify_records),
            "items": [],
        }

    matched_count = 0
    skipped_count = 0
    failed_count = 0
    items_result: list[dict[str, Any]] = []
    settings = get_settings()

    providers = [
        MusicBrainzProvider(settings=settings),
        AppleITunesProvider(settings=settings),
        DeezerProvider(settings=settings),
        SpotifyProvider(settings=settings),
    ] if fetch_art else []

    try:
        for idx, file_path in enumerate(audio_files):
            file_percent = (idx / total_files) * 100.0
            emit_progress(
                stage="match_spotify",
                file=str(file_path),
                percent=file_percent,
                message=f"Matching {file_path.name} against {len(spotify_records)} Spotify tracks...",
            )

            try:
                scan_res = inspect_audio(file_path)
                if scan_res.audio_format in ("wav", "wave", "aiff", "aif"):
                    if not convert_wav:
                        skipped_count += 1
                        items_result.append({
                            "file": str(file_path),
                            "status": "skipped",
                            "reason": "WAV conversion disabled",
                        })
                        continue
                    if dry_run:
                        emit_progress(
                            stage="dry_run",
                            file=str(file_path),
                            percent=file_percent,
                            message=f"[DRY-RUN] Would convert {file_path.name} to FLAC",
                        )
                    else:
                        file_path = convert_to_flac(file_path)
                        scan_res = inspect_audio(file_path)

                match_res = match_file_to_spotify(
                    file_path=file_path,
                    spotify_records=spotify_records,
                    threshold=threshold,
                    overwrite=overwrite,
                    scan_result=scan_res,
                )

                if match_res.is_match and match_res.spotify_record and match_res.metadata_to_inject:
                    art_bytes = None
                    art_mime = None
                    if fetch_art and match_res.metadata_to_inject.cover_art_url and providers:
                        for p in providers:
                            art_res = await p.fetch_cover_art(match_res.metadata_to_inject.cover_art_url)
                            if art_res:
                                art_bytes, art_mime = art_res
                                break

                    if dry_run:
                        matched_count += 1
                        items_result.append({
                            "file": str(file_path),
                            "status": "dry_run",
                            "matched_title": match_res.spotify_record.title,
                            "matched_artist": match_res.spotify_record.artist,
                            "matched_album": match_res.spotify_record.album,
                            "similarity_score": match_res.similarity_score,
                            "gaps_filled": match_res.missing_gaps_filled,
                            "overwritten_tags": match_res.overwritten_tags,
                            "metadata": serialize_track_metadata(match_res.metadata_to_inject),
                        })
                    else:
                        inject_metadata(
                            file_path,
                            match_res.metadata_to_inject,
                            cover_art_bytes=art_bytes,
                            cover_art_mime=art_mime,
                            overwrite_existing=overwrite,
                            overwrite_art=overwrite_art,
                        )
                        matched_count += 1
                        items_result.append({
                            "file": str(file_path),
                            "status": "injected",
                            "matched_title": match_res.spotify_record.title,
                            "matched_artist": match_res.spotify_record.artist,
                            "matched_album": match_res.spotify_record.album,
                            "similarity_score": match_res.similarity_score,
                            "gaps_filled": match_res.missing_gaps_filled,
                            "overwritten_tags": match_res.overwritten_tags,
                            "metadata": serialize_track_metadata(match_res.metadata_to_inject),
                        })
                else:
                    skipped_count += 1
                    items_result.append({
                        "file": str(file_path),
                        "status": "skipped",
                        "similarity_score": match_res.similarity_score,
                        "best_candidate": match_res.spotify_record.title if match_res.spotify_record else None,
                        "reason": f"Similarity below threshold ({match_res.similarity_score:.2f} < {threshold:.2f})",
                    })
            except Exception as e:
                failed_count += 1
                items_result.append({
                    "file": str(file_path),
                    "status": "error",
                    "error": str(e),
                })
    finally:
        for p in providers:
            await p.close()

    emit_progress(
        stage="complete",
        file="",
        percent=100.0,
        message=f"Spotify match complete: {matched_count} matched, {skipped_count} skipped, {failed_count} failed.",
    )

    return {
        "processed": total_files,
        "matched": matched_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "records_loaded": len(spotify_records),
        "items": items_result,
    }


async def run_convert_command(
    paths: list[str],
    output_dir: str | None = None,
    inject_tags: bool = True,
    delete_original: bool = False,
    compression_level: int = 8,
    threshold: float = 0.70,
    dry_run: bool = False,
    recursive: bool = True,
) -> dict[str, Any]:
    """Convert uncompressed audio files (WAV, AIFF) to FLAC."""
    wav_exts = {".wav", ".wave", ".aiff", ".aif"}
    source_files: list[Path] = []
    out_dir_path = Path(output_dir).resolve() if output_dir else None

    for p_str in paths:
        target = Path(p_str).resolve()
        if not target.exists():
            continue
        if target.is_file() and target.suffix.lower() in wav_exts:
            source_files.append(target)
        elif target.is_dir():
            pattern = "**/*" if recursive else "*"
            for candidate in sorted(target.glob(pattern)):
                if candidate.is_file() and candidate.suffix.lower() in wav_exts:
                    source_files.append(candidate)

    # Deduplicate
    seen: set[str] = set()
    unique_sources: list[Path] = []
    for f in source_files:
        norm = str(f)
        if norm not in seen:
            seen.add(norm)
            unique_sources.append(f)

    total_files = len(unique_sources)
    if total_files == 0:
        return {"converted": 0, "failed": 0, "items": []}

    settings = get_settings()
    providers = [
        MusicBrainzProvider(settings=settings),
        AppleITunesProvider(settings=settings),
        DeezerProvider(settings=settings),
        SpotifyProvider(settings=settings),
        DiscogsProvider(settings=settings),
    ] if inject_tags else []

    converted_count = 0
    failed_count = 0
    items_result: list[dict[str, Any]] = []

    try:
        for idx, src_file in enumerate(unique_sources):
            file_percent = (idx / total_files) * 100.0
            dest = (
                (out_dir_path / f"{src_file.stem}.flac")
                if out_dir_path
                else src_file.with_suffix(".flac")
            )

            emit_progress(
                stage="convert",
                file=str(src_file),
                percent=file_percent,
                message=f"Converting {src_file.name} to {dest.name}...",
            )

            if dry_run:
                items_result.append({
                    "source": str(src_file),
                    "destination": str(dest),
                    "status": "dry_run",
                })
                converted_count += 1
                continue

            try:
                converted_path = convert_to_flac(
                    src_file,
                    output_path=dest,
                    delete_original=delete_original,
                    compression_level=compression_level,
                )
                converted_count += 1
                item_entry: dict[str, Any] = {
                    "source": str(src_file),
                    "destination": str(converted_path),
                    "status": "converted",
                }

                if inject_tags and providers:
                    emit_progress(
                        stage="convert",
                        file=str(converted_path),
                        percent=file_percent + (100.0 / total_files) * 0.5,
                        message=f"Resolving metadata for {converted_path.name}...",
                    )
                    inject_res = await run_inject_command(
                        paths=[str(converted_path)],
                        threshold=threshold,
                        dry_run=False,
                        overwrite=False,
                        convert_wav=False,
                    )
                    item_entry["injection"] = inject_res

                items_result.append(item_entry)
            except Exception as e:
                failed_count += 1
                items_result.append({
                    "source": str(src_file),
                    "status": "error",
                    "error": str(e),
                })
                emit_error(f"Failed to convert {src_file.name}: {e}", file=str(src_file))
    finally:
        for p in providers:
            await p.close()

    emit_progress(
        stage="finished",
        file="",
        percent=100.0,
        message=f"Conversion finished: {converted_count} converted, {failed_count} failed.",
    )

    return {
        "converted": converted_count,
        "failed": failed_count,
        "items": items_result,
    }


def get_env_file_path() -> Path:
    """Resolve .env location deterministically: cwd if present, otherwise repo root."""
    cwd_env = Path(".env")
    if cwd_env.is_file():
        return cwd_env
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / ".env"
    repo_env = Path(__file__).resolve().parents[2] / ".env"
    if repo_env.is_file():
        return repo_env
    return cwd_env


def get_env_settings() -> dict[str, Any]:
    """Read .env configuration file and return raw and active settings."""
    env_path = get_env_file_path()
    raw_lines: dict[str, str] = {}
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                raw_lines[k.strip()] = v.strip().strip("'\"")

    settings = get_settings(env_file=env_path)
    return {
        "ACOUSTID_API_KEY": raw_lines.get(
            "ACOUSTID_API_KEY", settings.acoustid_api_key or ""
        ),
        "SPOTIFY_CLIENT_ID": raw_lines.get(
            "SPOTIFY_CLIENT_ID", settings.spotify_client_id or ""
        ),
        "SPOTIFY_CLIENT_SECRET": raw_lines.get(
            "SPOTIFY_CLIENT_SECRET", settings.spotify_client_secret or ""
        ),
        "DISCOGS_TOKEN": raw_lines.get(
            "DISCOGS_TOKEN", settings.discogs_token or ""
        ),
        "SONGLINK_API_KEY": raw_lines.get(
            "SONGLINK_API_KEY", settings.songlink_api_key or ""
        ),
        "MUSICBRAINZ_USER_AGENT": raw_lines.get(
            "MUSICBRAINZ_USER_AGENT", settings.musicbrainz_user_agent
        ),
        "RATE_LIMIT_DELAY": float(
            raw_lines.get("RATE_LIMIT_DELAY", settings.rate_limit_delay)
        ),
        "COVER_ART_MIN_RESOLUTION": int(
            raw_lines.get("COVER_ART_MIN_RESOLUTION", settings.cover_art_min_resolution)
        ),
        "CONFIDENCE_THRESHOLD": float(
            raw_lines.get("CONFIDENCE_THRESHOLD", settings.confidence_threshold)
        ),
        "REQUEST_TIMEOUT": float(
            raw_lines.get("REQUEST_TIMEOUT", settings.request_timeout)
        ),
        "FPCALC_PATH": raw_lines.get("FPCALC_PATH", settings.fpcalc_path),
    }


def save_env_settings(updates: dict[str, Any]) -> dict[str, Any]:
    """Save or update .env key-value pairs while preserving formatting."""
    env_path = get_env_file_path()
    lines: list[str] = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    keys_written: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            key = k.strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                keys_written.add(key)
                continue
        new_lines.append(line)

    # Append any keys that weren't already in the file
    for k, v in updates.items():
        if k not in keys_written:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    for k, v in updates.items():
        os.environ[k] = str(v)
    return get_env_settings()


async def dispatch_command(action: str, params: dict[str, Any]) -> None:
    """Dispatch a single command and emit result or error."""
    try:
        if action == "health":
            res = await asyncio.to_thread(run_health_check)
            emit_result("health", res)
        elif action == "scan":
            paths = params.get("paths", [])
            recursive = params.get("recursive", True)
            only_incomplete = params.get("only_incomplete", False)
            res = await asyncio.to_thread(run_scan_command, paths, recursive, only_incomplete)
            emit_result("scan", res)
        elif action == "inspect":
            path = params.get("path", "")
            include_art = params.get("include_art_base64", True)
            res = await asyncio.to_thread(run_inspect_command, path, include_art)
            emit_result("inspect", res)
        elif action == "fingerprint":
            path = params.get("path", "")
            res = await asyncio.to_thread(run_fingerprint_command, path)
            emit_result("fingerprint", res)
        elif action == "inject":
            paths = params.get("paths", [])
            threshold = float(params.get("threshold", 0.70))
            dry_run = bool(params.get("dry_run", False))
            overwrite = bool(params.get("overwrite", False))
            convert_wav = bool(params.get("convert_wav", True))
            recursive = bool(params.get("recursive", True))
            song_link = params.get("song_link")
            res = await run_inject_command(
                paths=paths,
                threshold=threshold,
                dry_run=dry_run,
                overwrite=overwrite,
                convert_wav=convert_wav,
                recursive=recursive,
                song_link=song_link,
            )
            emit_result("inject", res)
        elif action == "convert":
            paths = params.get("paths", [])
            output_dir = params.get("output_dir")
            inject_tags = bool(params.get("inject_tags", True))
            delete_orig = bool(params.get("delete_original", False))
            comp_lvl = int(params.get("compression_level", 8))
            threshold = float(params.get("threshold", 0.70))
            dry_run = bool(params.get("dry_run", False))
            recursive = bool(params.get("recursive", True))
            res = await run_convert_command(
                paths=paths,
                output_dir=output_dir,
                inject_tags=inject_tags,
                delete_original=delete_orig,
                compression_level=comp_lvl,
                threshold=threshold,
                dry_run=dry_run,
                recursive=recursive,
            )
            emit_result("convert", res)
        elif action in ("match_spotify", "import_spotify"):
            paths = params.get("paths", [])
            data_path = params.get("data_path", "")
            threshold = float(params.get("threshold", 0.70))
            dry_run = bool(params.get("dry_run", False))
            overwrite = bool(params.get("overwrite", False))
            overwrite_art = bool(params.get("overwrite_art", False))
            fetch_art = bool(params.get("fetch_art", False))
            convert_wav = bool(params.get("convert_wav", True))
            recursive = bool(params.get("recursive", True))
            res = await run_match_spotify_command(
                paths=paths,
                data_path=data_path,
                threshold=threshold,
                dry_run=dry_run,
                overwrite=overwrite,
                overwrite_art=overwrite_art,
                fetch_art=fetch_art,
                convert_wav=convert_wav,
                recursive=recursive,
            )
            emit_result(action, res)
        elif action == "get_env":
            emit_result("get_env", get_env_settings())
        elif action == "set_env":
            settings = params.get("settings", {})
            emit_result("set_env", save_env_settings(settings))
        else:
            emit_error(f"Unknown action: {action}", action=action)
    except Exception as exc:
        emit_error(f"Action '{action}' failed: {exc}", action=action)


def main() -> None:
    """CLI and Stdio entry point for the Python bridge."""
    # Scenario A: Invocation with command-line arguments:
    # python -m flac_injector.bridge <action> '[json_payload]' OR '-' to read from stdin
    if len(sys.argv) > 1 and sys.argv[1] not in ("--interactive", "-i"):
        action = sys.argv[1]
        params: dict[str, Any] = {}
        if len(sys.argv) > 2:
            arg = sys.argv[2]
            if arg == "-":
                raw_input = sys.stdin.read()
                if raw_input.strip():
                    try:
                        params = json.loads(raw_input)
                    except json.JSONDecodeError as err:
                        emit_error(f"Invalid JSON parameters from stdin: {err}", action=action)
                        sys.exit(1)
            else:
                try:
                    params = json.loads(arg)
                except json.JSONDecodeError as err:
                    emit_error(f"Invalid JSON parameters: {err}", action=action)
                    sys.exit(1)
        else:
            try:
                if not sys.stdin.isatty():
                    raw_input = sys.stdin.read()
                    if raw_input.strip():
                        params = json.loads(raw_input)
            except Exception:
                pass
        asyncio.run(dispatch_command(action, params))
        return

    # Scenario B: Stdio stream loop (reads NDJSON commands from stdin)
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            action = req.get("action", "")
            params = req.get("params", {})
            asyncio.run(dispatch_command(action, params))
        except json.JSONDecodeError as e:
            emit_error(f"Malformed JSON command: {e}")
        except Exception as e:
            emit_error(f"Bridge loop failure: {e}")


if __name__ == "__main__":
    main()
