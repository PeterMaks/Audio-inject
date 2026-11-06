"""Command Line Interface for flac-meta-injector using Typer and Rich."""

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TextColumn
from rich.table import Table

from flac_injector.artwork import ArtworkCache
from flac_injector.config import get_settings
from flac_injector.converter import convert_to_flac
from flac_injector.fingerprint import generate_fingerprint, parse_filename_metadata
from flac_injector.merger import aggregate_candidates
from flac_injector.models import TrackMetadata
from flac_injector.providers.apple_itunes import AppleITunesProvider
from flac_injector.providers.deezer import DeezerProvider
from flac_injector.providers.discogs import DiscogsProvider
from flac_injector.providers.musicbrainz import MusicBrainzProvider
from flac_injector.providers.songlink import SonglinkProvider
from flac_injector.providers.spotify import SpotifyProvider
from flac_injector.scanner import inspect_audio, scan_path
from flac_injector.spotify_import import load_spotify_data, match_file_to_spotify
from flac_injector.subprocess_patch import install_windows_headless_subprocess_patch
from flac_injector.writer import clean_embedded_art, inject_metadata

# Ensure all child subprocesses on Windows are silent and detached from console
install_windows_headless_subprocess_patch()

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = typer.Typer(
    name="flac-meta-injector",
    help="Production-grade audio metadata & cover art injector (FLAC & MP3) and WAV converter.",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


@app.command()
def scan(
    target: Annotated[
        Path,
        typer.Argument(help="Path to an audio file or directory (FLAC, MP3, WAV)."),
    ],
    recursive: Annotated[
        bool,
        typer.Option("--recursive/--no-recursive", "-r", help="Scan subdirectories recursively."),
    ] = True,
    only_incomplete: Annotated[
        bool,
        typer.Option("--only-incomplete", "-i", help="Display only files missing tags or art."),
    ] = False,
) -> None:
    """Scan audio files (FLAC, MP3, WAV) and report metadata and cover art completeness."""
    if not target.exists():
        console.print(f"[bold red]Target path does not exist:[/bold red] {target}")
        raise typer.Exit(code=1)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning audio files...", total=None)
        results = scan_path(target, recursive=recursive)
        progress.update(task, completed=True)

    if not results:
        console.print("[yellow]No supported audio files found in the specified path.[/yellow]")
        return

    table = Table(title="Audio Metadata Scan Results", header_style="bold cyan")
    table.add_column("Track / Path", style="dim")
    table.add_column("Format", justify="center")
    table.add_column("Title", style="bold")
    table.add_column("Artist")
    table.add_column("Album")
    table.add_column("Cover Art", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Missing Fields")

    incomplete_count = 0
    format_counts: dict[str, int] = {}
    for res in results:
        fmt = res.audio_format.upper()
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

        if only_incomplete and not res.is_incomplete:
            continue

        if res.is_incomplete:
            incomplete_count += 1
            status = "[bold red]INCOMPLETE[/bold red]"
        else:
            status = "[bold green]COMPLETE[/bold green]"

        art_status = (
            f"[green]OK ({res.cover_art_info['width']}x{res.cover_art_info['height']})[/green]"
            if res.has_cover_art and res.cover_art_info
            else "[red]MISSING[/red]"
        )

        title = res.existing_tags.get("TITLE", ["-"])[0]
        artist = res.existing_tags.get("ARTIST", ["-"])[0]
        album = res.existing_tags.get("ALBUM", ["-"])[0]
        missing = ", ".join(res.missing_fields) if res.missing_fields else "-"

        table.add_row(
            res.path.name,
            f"[cyan]{fmt}[/cyan]",
            title,
            artist,
            album,
            art_status,
            status,
            f"[yellow]{missing}[/yellow]",
        )

    console.print(table)
    fmt_summary = "  |  ".join([f"{k}: [bold]{v}[/bold]" for k, v in sorted(format_counts.items())])
    console.print(
        Panel(
            f"Total Scanned: [bold]{len(results)}[/bold] ({fmt_summary})  |  "
            f"Complete: [bold green]{len(results) - incomplete_count}[/bold green]  |  "
            f"Incomplete: [bold red]{incomplete_count}[/bold red]",
            title="Scan Summary",
            expand=False,
        )
    )


@app.command()
def inspect(
    file_path: Annotated[
        Path,
        typer.Argument(help="Path to the audio file (FLAC, MP3, WAV) to inspect in detail."),
    ],
) -> None:
    """Inspect detailed tags, properties, and cover art blocks of an audio file."""
    if not file_path.is_file():
        console.print(f"[bold red]File not found:[/bold red] {file_path}")
        raise typer.Exit(code=1)

    res = inspect_audio(file_path)

    # Audio stream properties
    mins = int(res.duration_seconds // 60)
    secs = int(res.duration_seconds % 60)
    audio_info = (
        f"Path: [bold]{res.path}[/bold]\n"
        f"Format: [bold cyan]{res.audio_format.upper()}[/bold cyan]\n"
        f"Duration: [bold]{mins:02d}:{secs:02d}[/bold] ({res.duration_seconds:.2f}s)\n"
        f"Specs: [bold]{res.sample_rate} Hz[/bold], {res.channels} Ch, {res.bits_per_sample}-bit"
    )
    console.print(Panel(audio_info, title="Audio Stream Properties", expand=False))

    if res.audio_format == "wav":
        console.print(
            "[yellow]WAV file detected (uncompressed audio container). "
            "Use 'flac-meta-injector convert' to encode to FLAC before tagging.[/yellow]"
        )
        return

    # Metadata tags table
    tag_header = "Vorbis Comments" if res.audio_format == "flac" else "ID3 Tags"
    tags_table = Table(title=tag_header, header_style="bold magenta")
    tags_table.add_column("Tag Key", style="cyan", no_wrap=True)
    tags_table.add_column("Value(s)")

    if res.existing_tags:
        for k, v in sorted(res.existing_tags.items()):
            tags_table.add_row(k, " // ".join(v))
    else:
        tags_table.add_row("[italic dim]No tags[/italic dim]", "-")
    console.print(tags_table)

    # Picture Block / APIC Panel
    if res.has_cover_art and res.cover_art_info:
        res_w = res.cover_art_info["width"]
        res_h = res.cover_art_info["height"]
        art_desc = (
            f"Type: [bold]Cover (front)[/bold] ({res.cover_art_info['type']})\n"
            f"MIME: [bold]{res.cover_art_info['mime']}[/bold]\n"
            f"Resolution: [bold]{res_w}x{res_h}[/bold]\n"
            f"Bit Depth: [bold]{res.cover_art_info['depth']}-bit[/bold]\n"
            f"Size: [bold]{res.cover_art_info['size_bytes'] / 1024:.1f} KB[/bold]"
        )
        is_flac = res.audio_format == "flac"
        title_box = "Embedded Picture Block" if is_flac else "Attached Picture (APIC)"
        console.print(Panel(art_desc, title=title_box, expand=False))
    else:
        console.print("[yellow]No embedded front cover art detected in this audio file.[/yellow]")


@app.command()
def fingerprint(
    file_path: Annotated[
        Path,
        typer.Argument(help="Path to the audio file to fingerprint."),
    ],
) -> None:
    """Generate Chromaprint fingerprint and parse filename heuristics."""
    if not file_path.is_file():
        console.print(f"[bold red]File not found:[/bold red] {file_path}")
        raise typer.Exit(code=1)

    fp = generate_fingerprint(file_path)
    parsed = parse_filename_metadata(file_path)

    console.print(
        Panel(
            f"File: [bold]{file_path.name}[/bold]\n"
            f"Duration: [bold]{fp.duration:.2f}s[/bold]\n"
            f"Chromaprint Fingerprint:\n[dim cyan]{fp.fingerprint[:80]}...[/dim cyan]",
            title="Acoustic Fingerprint",
            expand=False,
        )
    )

    hints_table = Table(title="Parsed Heuristic Metadata Hints", header_style="bold green")
    hints_table.add_column("Field", style="cyan")
    hints_table.add_column("Value")
    for k, v in parsed.items():
        hints_table.add_row(k.capitalize(), str(v) if v is not None else "[dim]None[/dim]")
    console.print(hints_table)


async def _resolve_and_inject_track(
    file_path: Path,
    providers: list[Any],
    threshold: float,
    dry_run: bool,
    overwrite: bool,
    convert_wav: bool = True,
    overwrite_art: bool = False,
    overwrite_unknown: bool = False,
    overwrite_album: str | None = None,
    art_cache: ArtworkCache | None = None,
    song_link: str | None = None,
) -> bool:
    """Resolve metadata across providers and inject into FLAC or MP3 (or convert WAV)."""
    scan_res = inspect_audio(file_path)

    # If it is a WAV file and conversion is enabled, convert to FLAC first
    if scan_res.audio_format in ("wav", "wave", "aiff", "aif"):
        if not convert_wav:
            console.print(
                f"[yellow]Skipping WAV file (conversion disabled):[/yellow] {file_path.name}"
            )
            return False
        if dry_run:
            console.print(f"[dim cyan][DRY-RUN] Would convert {file_path.name} to FLAC[/dim cyan]")
        else:
            console.print(f"[cyan]Converting WAV to FLAC:[/cyan] {file_path.name}...")
            file_path = convert_to_flac(file_path)
            scan_res = inspect_audio(file_path)

    existing_album = scan_res.existing_tags.get("ALBUM", [""])[0].strip()
    is_unknown_album = not existing_album or existing_album.lower() in {
        "unknown",
        "unknown album",
        "untitled",
        "none",
        "no album",
        "placeholder",
    }

    matches_overwrite_album = bool(
        overwrite_album and existing_album.lower() == overwrite_album.strip().lower()
    )

    should_overwrite_this_track = (
        overwrite or (overwrite_unknown and is_unknown_album) or matches_overwrite_album
    )

    if not scan_res.is_incomplete and not should_overwrite_this_track and not overwrite_art:
        console.print(f"[dim]Skipping complete track:[/dim] {file_path.name}")
        return True

    # 1. Fingerprint
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
    mb_provider: MusicBrainzProvider | None = next(
        (p for p in providers if getattr(p, "name", "") == "musicbrainz"), None
    )
    apple_provider: AppleITunesProvider | None = next(
        (p for p in providers if getattr(p, "name", "") == "apple_itunes"), None
    )
    deezer_provider: DeezerProvider | None = next(
        (p for p in providers if getattr(p, "name", "") == "deezer"), None
    )
    spotify_provider: SpotifyProvider | None = next(
        (p for p in providers if getattr(p, "name", "") == "spotify"), None
    )
    discogs_provider: DiscogsProvider | None = next(
        (p for p in providers if getattr(p, "name", "") == "discogs"), None
    )
    songlink_provider: SonglinkProvider | None = next(
        (p for p in providers if getattr(p, "name", "") == "songlink"), None
    )

    # Step 0: Direct Song Link / Streaming URL lookup if provided or present in tags
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
        try:
            sl_candidates = await songlink_provider.lookup_by_url(direct_url)
            all_candidates.extend(sl_candidates)
        except Exception:
            pass

    # Step 1: Acoustic Fingerprint Lookup
    if fp and fp.fingerprint and mb_provider:
        mb_candidates = await mb_provider.lookup_by_fingerprint(fp.fingerprint, fp.duration)
        all_candidates.extend(mb_candidates)

    # Step 2: ISRC Lookup if any candidate has ISRC
    isrc = None
    for c in all_candidates:
        if c.isrc:
            isrc = c.isrc
            break

    if isrc:
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

    # Step 3: Query Lookup Fallback
    if not all_candidates and hints.get("title"):
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

    # Step 4: Waterfall Aggregation
    best = aggregate_candidates(
        all_candidates,
        scan_res.duration_seconds,
        hints,
        confidence_threshold=threshold,
    )

    if not best:
        console.print(
            f"[bold yellow]No confident metadata match found for:[/bold yellow] {file_path.name}"
        )
        return False

    console.print(
        f"[bold green]Resolved:[/bold green] {file_path.name} -> "
        f"[bold]{best.artist} - {best.title}[/bold] "
        f"([cyan]{best.album}[/cyan], Score: {best.confidence_score:.2f})"
    )

    # Step 5: Fetch Cover Art if needed
    art_bytes = None
    art_mime = None
    should_fetch_art = (
        not scan_res.has_cover_art or overwrite or overwrite_art or should_overwrite_this_track
    )
    if best.cover_art_url and should_fetch_art:
        if art_cache:
            cached = art_cache.get(
                best.artist,
                best.album,
                best.isrc or best.musicbrainz_albumid,
            )
            if cached:
                art_bytes, art_mime = cached
        if not art_bytes:
            for p in providers:
                art_result = await p.fetch_cover_art(best.cover_art_url)
                if art_result:
                    art_bytes, art_mime = art_result
                    if art_cache:
                        art_cache.set(
                            best.artist,
                            best.album,
                            art_bytes,
                            art_mime,
                            best.isrc or best.musicbrainz_albumid,
                        )
                    break

    if dry_run:
        tag_count = (
            len(best.to_vorbis_comments())
            if scan_res.audio_format == "flac"
            else len(best.to_id3_dict())
        )
        art_desc = "cover art" if art_bytes else "no art"
        console.print(
            f"[dim cyan][DRY-RUN] Would inject {tag_count} tags "
            f"and {art_desc} into {file_path.suffix.upper()}[/dim cyan]"
        )
        return True

    # Step 6: Inject
    inject_metadata(
        file_path,
        best,
        cover_art_bytes=art_bytes,
        cover_art_mime=art_mime,
        overwrite_existing=should_overwrite_this_track,
        overwrite_art=(overwrite_art or should_overwrite_this_track),
    )
    console.print(f"[bold green][OK] Injected successfully:[/bold green] {file_path.name}")
    return True


@app.command()
def inject(
    target: Annotated[
        Path,
        typer.Argument(help="Path to an audio file or directory (FLAC, MP3, WAV)."),
    ],
    threshold: Annotated[
        float,
        typer.Option("--threshold", "-t", help="Minimum confidence threshold (0.0 to 1.0)."),
    ] = 0.70,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview metadata changes without writing to disk."),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Overwrite existing non-empty tags."),
    ] = False,
    overwrite_art: Annotated[
        bool,
        typer.Option(
            "--overwrite-art",
            help="Force re-resolving and replacing album art even if track is complete.",
        ),
    ] = False,
    overwrite_unknown: Annotated[
        bool,
        typer.Option(
            "--overwrite-unknown",
            help="Selectively overwrite tracks whose existing album is 'Unknown Album' or missing.",
        ),
    ] = False,
    overwrite_album: Annotated[
        str | None,
        typer.Option(
            "--overwrite-album",
            help=(
                "Selectively overwrite tracks whose existing album matches this specific name "
                "(e.g. 'Unknown Album')."
            ),
        ),
    ] = None,
    song_link: Annotated[
        str | None,
        typer.Option(
            "--song-link",
            "--url",
            help="Direct song.link or streaming platform URL to resolve metadata from.",
        ),
    ] = None,
    convert_wav: Annotated[
        bool,
        typer.Option(
            "--convert-wav/--no-convert-wav",
            help="Auto-convert WAV files to FLAC before injecting.",
        ),
    ] = True,
    recursive: Annotated[
        bool,
        typer.Option("--recursive/--no-recursive", "-r", help="Recurse into subdirectories."),
    ] = True,
) -> None:
    """Scan and inject standardized metadata and cover art into FLAC and MP3 files."""
    if not target.exists():
        console.print(f"[bold red]Target path does not exist:[/bold red] {target}")
        raise typer.Exit(code=1)

    settings = get_settings()
    allowed_exts = {".flac", ".mp3"}
    if convert_wav:
        allowed_exts.update({".wav", ".wave", ".aiff", ".aif"})

    if target.is_file():
        audio_files = [target] if target.suffix.lower() in allowed_exts else []
    else:
        glob_pat = "**/*" if recursive else "*"
        audio_files = [
            p
            for p in sorted(target.glob(glob_pat))
            if p.is_file() and p.suffix.lower() in allowed_exts
        ]

    if not audio_files:
        console.print("[yellow]No supported audio files found to process.[/yellow]")
        return

    async def _run_all() -> None:
        art_cache = ArtworkCache()
        providers = [
            MusicBrainzProvider(settings=settings),
            AppleITunesProvider(settings=settings),
            DeezerProvider(settings=settings),
            SpotifyProvider(settings=settings),
            DiscogsProvider(settings=settings),
            SonglinkProvider(settings=settings),
        ]
        try:
            for file_path in audio_files:
                await _resolve_and_inject_track(
                    file_path,
                    providers,
                    threshold,
                    dry_run,
                    overwrite,
                    convert_wav=convert_wav,
                    overwrite_art=overwrite_art,
                    overwrite_unknown=overwrite_unknown,
                    overwrite_album=overwrite_album,
                    art_cache=art_cache,
                    song_link=song_link,
                )
        finally:
            for p in providers:
                await p.close()

    asyncio.run(_run_all())


@app.command(name="match-spotify")
def match_spotify(
    target: Annotated[
        Path,
        typer.Argument(help="Path to an audio file or directory (FLAC, MP3, WAV)."),
    ],
    data_file: Annotated[
        Path | None,
        typer.Argument(help="Path to the Spotify CSV or JSON export file."),
    ] = None,
    data: Annotated[
        Path | None,
        typer.Option("--data", "-d", help="Path to the Spotify CSV or JSON export file."),
    ] = None,
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold", "-t", help="Minimum similarity threshold (0.0 to 1.0, default 0.70)."
        ),
    ] = 0.70,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Preview matches and metadata updates without modifying files."
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Overwrite existing non-empty tags instead of only filling missing gaps.",
        ),
    ] = False,
    overwrite_mismatched: Annotated[
        bool,
        typer.Option(
            "--overwrite-mismatched/--no-overwrite-mismatched",
            help=(
                "Overwrite existing metadata tags (artist, title, album) if they do not match "
                "or have low similarity to the filename / Spotify track."
            ),
        ),
    ] = True,
    overwrite_art: Annotated[
        bool,
        typer.Option(
            "--overwrite-art",
            help="Force overwriting album art if cover art is available from matched Spotify data.",
        ),
    ] = False,
    fetch_art: Annotated[
        bool,
        typer.Option(
            "--fetch-art",
            help="Attempt to fetch cover art from metadata providers for matched tracks.",
        ),
    ] = False,
    convert_wav: Annotated[
        bool,
        typer.Option(
            "--convert-wav/--no-convert-wav",
            help="Auto-convert WAV files to FLAC before matching.",
        ),
    ] = True,
    recursive: Annotated[
        bool,
        typer.Option("--recursive/--no-recursive", "-r", help="Recurse into subdirectories."),
    ] = True,
) -> None:
    """Compare and match audio files against exported Spotify data (CSV or JSON)."""
    # 1. Resolve data file path
    spotify_data_path = data or data_file
    if not spotify_data_path:
        console.print(
            "[bold red]Error:[/bold red] Please specify a valid Spotify CSV or JSON export file "
            "as an argument or via [bold]--data / -d[/bold]."
        )
        raise typer.Exit(code=1)

    if not spotify_data_path.exists():
        console.print(f"[bold red]Spotify data file not found:[/bold red] {spotify_data_path}")
        raise typer.Exit(code=1)

    # 2. Check target path
    if not target.exists():
        console.print(f"[bold red]Target path does not exist:[/bold red] {target}")
        raise typer.Exit(code=1)

    # 3. Load Spotify records
    try:
        spotify_records = load_spotify_data(spotify_data_path)
    except Exception as exc:
        console.print(f"[bold red]Failed to parse Spotify export file:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    if not spotify_records:
        console.print(
            f"[bold yellow]No valid track records found in:[/bold yellow] {spotify_data_path}"
        )
        return

    console.print(
        Panel(
            f"Loaded [bold green]{len(spotify_records)}[/bold green] track records from "
            f"[bold]{spotify_data_path.name}[/bold]\n"
            f"Matching against: [bold]{target}[/bold] "
            f"(Similarity Threshold: [bold cyan]{threshold:.2f}[/bold cyan])\n"
            f"Mode: [bold]{'FULL OVERWRITE' if overwrite else 'FILL METADATA GAPS ONLY'}[/bold]"
            f"{' [bold yellow][DRY-RUN PREVIEW][/bold yellow]' if dry_run else ''}",
            title="Spotify Metadata Matcher",
            expand=False,
        )
    )

    # 4. Enumerate audio files
    allowed_exts = {".flac", ".mp3"}
    if convert_wav:
        allowed_exts.update({".wav", ".wave", ".aiff", ".aif"})

    if target.is_file():
        audio_files = [target] if target.suffix.lower() in allowed_exts else []
    else:
        glob_pat = "**/*" if recursive else "*"
        audio_files = [
            p
            for p in sorted(target.glob(glob_pat))
            if p.is_file() and p.suffix.lower() in allowed_exts
        ]

    if not audio_files:
        console.print("[yellow]No supported audio files found to match.[/yellow]")
        return

    # 5. Matching & Injection Process
    matched_count = 0
    skipped_count = 0
    total_gaps_filled = 0

    table = Table(
        title=(
            f"Spotify Track Matching ({len(audio_files)} files vs {len(spotify_records)} records)"
        ),
        header_style="bold cyan",
    )
    table.add_column("Audio File", style="dim", no_wrap=True)
    table.add_column("Similarity", justify="center")
    table.add_column("Matched Title", style="bold")
    table.add_column("Matched Artist")
    table.add_column("Album")
    table.add_column("Gaps Filled / Overwritten")
    table.add_column("Status", justify="center")

    settings = get_settings()

    async def _process_files() -> None:
        nonlocal matched_count, skipped_count, total_gaps_filled
        providers = (
            [
                MusicBrainzProvider(settings=settings),
                AppleITunesProvider(settings=settings),
                DeezerProvider(settings=settings),
                SpotifyProvider(settings=settings),
            ]
            if fetch_art
            else []
        )

        try:
            for file_path in audio_files:
                # WAV conversion check
                scan_res = inspect_audio(file_path)
                if scan_res.audio_format in ("wav", "wave", "aiff", "aif"):
                    if not convert_wav:
                        continue
                    if dry_run:
                        console.print(
                            f"[dim cyan][DRY-RUN] Would convert {file_path.name} to FLAC[/dim cyan]"
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
                    overwrite_mismatched=overwrite_mismatched,
                )

                if match_res.is_match and match_res.spotify_record and match_res.metadata_to_inject:
                    matched_count += 1
                    total_gaps_filled += len(match_res.missing_gaps_filled)
                    score_pct = f"{match_res.similarity_score * 100:.1f}%"

                    gaps_desc: list[str] = []
                    if match_res.missing_gaps_filled:
                        filled_preview = ", ".join(match_res.missing_gaps_filled[:3])
                        gaps_desc.append(
                            f"[green]+{len(match_res.missing_gaps_filled)} gaps[/green] "
                            f"({filled_preview})"
                        )
                    if match_res.overwritten_tags:
                        overwritten_preview = ", ".join(match_res.overwritten_tags[:3])
                        gaps_desc.append(
                            f"[yellow]~{len(match_res.overwritten_tags)} overwrites[/yellow] "
                            f"({overwritten_preview})"
                        )
                    actions_str = " | ".join(gaps_desc) if gaps_desc else "[dim]No new tags[/dim]"

                    # Cover art fetching if requested
                    art_bytes = None
                    art_mime = None
                    if fetch_art and match_res.metadata_to_inject.cover_art_url and providers:
                        for p in providers:
                            art_res = await p.fetch_cover_art(
                                match_res.metadata_to_inject.cover_art_url
                            )
                            if art_res:
                                art_bytes, art_mime = art_res
                                break

                    if dry_run:
                        status = "[dim cyan]WOULD INJECT[/dim cyan]"
                    else:
                        inject_metadata(
                            file_path,
                            match_res.metadata_to_inject,
                            cover_art_bytes=art_bytes,
                            cover_art_mime=art_mime,
                            overwrite_existing=overwrite,
                            overwrite_art=overwrite_art,
                            overwrite_tags=match_res.overwritten_tags,
                        )
                        status = "[bold green]INJECTED[/bold green]"

                    table.add_row(
                        file_path.name,
                        f"[bold green]{score_pct}[/bold green]",
                        match_res.spotify_record.title,
                        match_res.spotify_record.artist,
                        match_res.spotify_record.album,
                        actions_str,
                        status,
                    )
                else:
                    skipped_count += 1
                    best_hint = (
                        f"{match_res.spotify_record.title} "
                        f"({match_res.similarity_score * 100:.1f}%)"
                        if match_res.spotify_record and match_res.similarity_score > 0
                        else "-"
                    )
                    table.add_row(
                        file_path.name,
                        f"[dim red]{match_res.similarity_score * 100:.1f}%[/dim red]"
                        if match_res.similarity_score > 0
                        else "[dim]-[/dim]",
                        f"[dim]{best_hint}[/dim]",
                        "-",
                        "-",
                        "-",
                        "[dim yellow]SKIPPED (< threshold)[/dim yellow]",
                    )
        finally:
            for p in providers:
                await p.close()

    asyncio.run(_process_files())

    console.print(table)
    summary_text = (
        f"Processed: [bold]{len(audio_files)}[/bold] file(s)  |  "
        f"Matched: [bold green]{matched_count}[/bold green]  |  "
        f"Unmatched / Skipped: [bold yellow]{skipped_count}[/bold yellow]  |  "
        f"Metadata Gaps Filled: [bold cyan]{total_gaps_filled}[/bold cyan]"
    )
    console.print(Panel(summary_text, title="Matching Summary", expand=False))


@app.command(name="import-spotify")
def import_spotify(
    target: Annotated[
        Path,
        typer.Argument(help="Path to an audio file or directory (FLAC, MP3, WAV)."),
    ],
    data_file: Annotated[
        Path | None,
        typer.Argument(help="Path to the Spotify CSV or JSON export file."),
    ] = None,
    data: Annotated[
        Path | None,
        typer.Option("--data", "-d", help="Path to the Spotify CSV or JSON export file."),
    ] = None,
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold", "-t", help="Minimum similarity threshold (0.0 to 1.0, default 0.70)."
        ),
    ] = 0.70,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Preview matches and metadata updates without modifying files."
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Overwrite existing non-empty tags instead of only filling missing gaps.",
        ),
    ] = False,
    overwrite_mismatched: Annotated[
        bool,
        typer.Option(
            "--overwrite-mismatched/--no-overwrite-mismatched",
            help=(
                "Overwrite existing metadata tags (artist, title, album) if they do not match "
                "or have low similarity to the filename / Spotify track."
            ),
        ),
    ] = True,
    overwrite_art: Annotated[
        bool,
        typer.Option(
            "--overwrite-art",
            help="Force overwriting album art if cover art is available from matched Spotify data.",
        ),
    ] = False,
    fetch_art: Annotated[
        bool,
        typer.Option(
            "--fetch-art",
            help="Attempt to fetch cover art from metadata providers for matched tracks.",
        ),
    ] = False,
    convert_wav: Annotated[
        bool,
        typer.Option(
            "--convert-wav/--no-convert-wav",
            help="Auto-convert WAV files to FLAC before matching.",
        ),
    ] = True,
    recursive: Annotated[
        bool,
        typer.Option("--recursive/--no-recursive", "-r", help="Recurse into subdirectories."),
    ] = True,
) -> None:
    """Alias for match-spotify: import Spotify export and fill metadata gaps in audio files."""
    match_spotify(
        target=target,
        data_file=data_file,
        data=data,
        threshold=threshold,
        dry_run=dry_run,
        overwrite=overwrite,
        overwrite_mismatched=overwrite_mismatched,
        overwrite_art=overwrite_art,
        fetch_art=fetch_art,
        convert_wav=convert_wav,
        recursive=recursive,
    )


@app.command()
def convert(
    target: Annotated[
        Path,
        typer.Argument(help="Path to a WAV file or directory containing audio files to convert."),
    ],
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help="Optional destination directory for converted FLACs.",
        ),
    ] = None,
    inject_tags: Annotated[
        bool,
        typer.Option(
            "--inject/--no-inject",
            help="Automatically resolve and inject metadata after conversion.",
        ),
    ] = True,
    delete_original: Annotated[
        bool,
        typer.Option(
            "--delete-original",
            help="Delete source WAV files after successful conversion.",
        ),
    ] = False,
    compression_level: Annotated[
        int,
        typer.Option("--compression-level", "-c", help="FLAC compression level (0-12, default 8)."),
    ] = 8,
    threshold: Annotated[
        float,
        typer.Option("--threshold", "-t", help="Minimum confidence threshold for auto-injection."),
    ] = 0.70,
    recursive: Annotated[
        bool,
        typer.Option("--recursive/--no-recursive", "-r", help="Recurse into subdirectories."),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview conversions without writing files."),
    ] = False,
) -> None:
    """Convert WAV / uncompressed audio files into FLAC and optionally inject tags."""
    if not target.exists():
        console.print(f"[bold red]Target path does not exist:[/bold red] {target}")
        raise typer.Exit(code=1)

    wav_exts = {".wav", ".wave", ".aiff", ".aif"}
    if target.is_file():
        source_files = [target] if target.suffix.lower() in wav_exts else []
    else:
        pattern = "**/*" if recursive else "*"
        source_files = [
            p for p in sorted(target.glob(pattern)) if p.is_file() and p.suffix.lower() in wav_exts
        ]

    if not source_files:
        console.print("[yellow]No WAV / uncompressed audio files found to convert.[/yellow]")
        return

    console.print(f"[bold]Found {len(source_files)} audio file(s) to convert to FLAC.[/bold]")

    settings = get_settings()

    async def _run_convert_and_inject() -> None:
        providers = (
            [
                MusicBrainzProvider(settings=settings),
                AppleITunesProvider(settings=settings),
                DeezerProvider(settings=settings),
                SpotifyProvider(settings=settings),
                DiscogsProvider(settings=settings),
                SonglinkProvider(settings=settings),
            ]
            if inject_tags
            else []
        )

        try:
            for src_file in source_files:
                dest = (
                    (output_dir / f"{src_file.stem}.flac")
                    if output_dir
                    else src_file.with_suffix(".flac")
                )
                if dry_run:
                    console.print(
                        f"[dim cyan][DRY-RUN] Would convert {src_file.name} -> {dest.name} "
                        f"(Compression: {compression_level})[/dim cyan]"
                    )
                    continue

                console.print(
                    f"[cyan]Converting:[/cyan] {src_file.name} -> [bold]{dest.name}[/bold]"
                )
                converted_path = convert_to_flac(
                    src_file,
                    output_path=dest,
                    delete_original=delete_original,
                    compression_level=compression_level,
                )
                console.print(
                    f"[bold green][OK] Converted successfully:[/bold green] {converted_path.name}"
                )

                if inject_tags and providers:
                    console.print(f"[cyan]Injecting metadata into:[/cyan] {converted_path.name}...")
                    await _resolve_and_inject_track(
                        converted_path,
                        providers,
                        threshold=threshold,
                        dry_run=False,
                        overwrite=False,
                    )
        finally:
            for p in providers:
                await p.close()

    asyncio.run(_run_convert_and_inject())


@app.command(name="clean-art")
def clean_art(
    target: Annotated[
        Path,
        typer.Argument(help="Path to an audio file or directory to clean duplicate art."),
    ],
    remove_folder_art: Annotated[
        bool,
        typer.Option(
            "--remove-folder-art",
            help="Remove loose images (folder.jpg/cover.jpg) that override track art.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview art cleanup without writing to disk."),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option("--recursive/--no-recursive", "-r", help="Recurse into subdirectories."),
    ] = True,
) -> None:
    """Deduplicate picture blocks, purge legacy picture tags, and clean loose folder images."""
    if not target.exists():
        console.print(f"[bold red]Target path does not exist:[/bold red] {target}")
        raise typer.Exit(code=1)

    audio_exts = {".flac", ".mp3"}
    if target.is_file():
        audio_files = [target] if target.suffix.lower() in audio_exts else []
        directories = [target.parent]
    else:
        glob_pat = "**/*" if recursive else "*"
        audio_files = [
            p
            for p in sorted(target.glob(glob_pat))
            if p.is_file() and p.suffix.lower() in audio_exts
        ]
        directories = (
            [target] if not recursive else [d for d in [target, *target.glob("**/")] if d.is_dir()]
        )

    cleaned_count = 0
    for f in audio_files:
        res = clean_embedded_art(f, dry_run=dry_run)
        if res["modified"]:
            cleaned_count += 1
            action = (
                "[dim cyan][DRY-RUN] Would clean[/dim cyan]"
                if dry_run
                else "[bold green][OK] Cleaned art:[/bold green]"
            )
            console.print(
                f"{action} {f.name} "
                f"({res['pictures_before']} -> {res['pictures_after']} pic block(s))"
            )

    console.print(
        f"[bold]Processed {len(audio_files)} audio file(s): "
        f"{cleaned_count} had duplicate art cleaned.[/bold]"
    )

    # Check for loose folder art
    loose_art_names = {
        "folder.jpg",
        "folder.png",
        "cover.jpg",
        "cover.png",
        "albumart.jpg",
        "albumart.png",
        "front.jpg",
        "front.png",
    }
    found_loose: list[Path] = []
    for d in directories:
        for item in d.glob("*"):
            if item.is_file():
                name_lower = item.name.lower()
                if name_lower in loose_art_names or (
                    name_lower.startswith("albumart_") and name_lower.endswith(".jpg")
                ):
                    found_loose.append(item)

    if found_loose:
        console.print(
            f"\n[bold yellow]Found {len(found_loose)} loose folder image(s):[/bold yellow]"
        )
        for img in found_loose:
            if remove_folder_art:
                if dry_run:
                    console.print(f"[dim cyan][DRY-RUN] Would remove loose image:[/dim cyan] {img}")
                else:
                    img.unlink()
                    console.print(f"[bold red]Removed loose image:[/bold red] {img}")
            else:
                console.print(
                    f"  [yellow]• {img}[/yellow] (Note: Causes media players to show same cover. "
                    "Use [bold]--remove-folder-art[/bold] to delete)."
                )


if __name__ == "__main__":
    app()
