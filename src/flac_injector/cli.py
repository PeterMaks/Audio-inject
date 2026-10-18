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

from flac_injector.config import get_settings
from flac_injector.fingerprint import generate_fingerprint, parse_filename_metadata
from flac_injector.merger import aggregate_candidates
from flac_injector.models import TrackMetadata
from flac_injector.providers.apple_itunes import AppleITunesProvider
from flac_injector.providers.deezer import DeezerProvider
from flac_injector.providers.musicbrainz import MusicBrainzProvider
from flac_injector.providers.spotify import SpotifyProvider
from flac_injector.scanner import inspect_flac, scan_path
from flac_injector.writer import inject_metadata

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
    help="Production-grade FLAC metadata and cover art injector.",
    add_completion=False,
)
console = Console()


@app.command()
def scan(
    target: Annotated[
        Path,
        typer.Argument(help="Path to a FLAC file or directory containing FLAC files."),
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
    """Scan local FLAC tracks and report metadata and cover art completeness."""
    if not target.exists():
        console.print(f"[bold red]Target path does not exist:[/bold red] {target}")
        raise typer.Exit(code=1)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning FLAC files...", total=None)
        results = scan_path(target, recursive=recursive)
        progress.update(task, completed=True)

    if not results:
        console.print("[yellow]No FLAC files found in the specified path.[/yellow]")
        return

    table = Table(title="FLAC Metadata Scan Results", header_style="bold cyan")
    table.add_column("Track / Path", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Artist")
    table.add_column("Album")
    table.add_column("Cover Art", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Missing Fields")

    incomplete_count = 0
    for res in results:
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
            title,
            artist,
            album,
            art_status,
            status,
            f"[yellow]{missing}[/yellow]",
        )

    console.print(table)
    console.print(
        Panel(
            f"Total Scanned: [bold]{len(results)}[/bold]  |  "
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
        typer.Argument(help="Path to the FLAC file to inspect in detail."),
    ],
) -> None:
    """Inspect detailed Vorbis Comment tags and Picture blocks of a FLAC file."""
    if not file_path.is_file():
        console.print(f"[bold red]File not found:[/bold red] {file_path}")
        raise typer.Exit(code=1)

    res = inspect_flac(file_path)

    # Audio details panel
    mins = int(res.duration_seconds // 60)
    secs = int(res.duration_seconds % 60)
    audio_info = (
        f"Path: [bold]{res.path}[/bold]\n"
        f"Duration: [bold]{mins:02d}:{secs:02d}[/bold] ({res.duration_seconds:.2f}s)\n"
        f"Format: [bold]{res.sample_rate} Hz[/bold], {res.channels} Ch, {res.bits_per_sample}-bit"
    )
    console.print(Panel(audio_info, title="FLAC Audio Stream Properties", expand=False))

    # Vorbis Comments Table
    tags_table = Table(title="Vorbis Comments", header_style="bold magenta")
    tags_table.add_column("Tag Key", style="cyan", no_wrap=True)
    tags_table.add_column("Value(s)")

    if res.existing_tags:
        for k, v in sorted(res.existing_tags.items()):
            tags_table.add_row(k, " // ".join(v))
    else:
        tags_table.add_row("[italic dim]No tags[/italic dim]", "—")
    console.print(tags_table)

    # Picture Block Panel
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
        console.print(Panel(art_desc, title="Embedded Picture Block", expand=False))
    else:
        console.print("[yellow]No embedded Picture blocks detected in this FLAC file.[/yellow]")


@app.command()
def fingerprint(
    file_path: Annotated[
        Path,
        typer.Argument(help="Path to the FLAC file to fingerprint."),
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
) -> bool:
    """Resolve metadata across providers and inject into file."""
    scan_res = inspect_flac(file_path)
    if not scan_res.is_incomplete and not overwrite:
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
    mb_provider: MusicBrainzProvider = providers[0]
    apple_provider: AppleITunesProvider = providers[1]
    deezer_provider: DeezerProvider = providers[2]
    spotify_provider: SpotifyProvider = providers[3]

    # Step 1: Acoustic Fingerprint Lookup
    if fp and fp.fingerprint:
        mb_candidates = await mb_provider.lookup_by_fingerprint(fp.fingerprint, fp.duration)
        all_candidates.extend(mb_candidates)

    # Step 2: ISRC Lookup if any candidate has ISRC
    isrc = None
    for c in all_candidates:
        if c.isrc:
            isrc = c.isrc
            break

    if isrc:
        tasks = [
            apple_provider.lookup_by_isrc(isrc),
            deezer_provider.lookup_by_isrc(isrc),
            spotify_provider.lookup_by_isrc(isrc),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_candidates.extend(r)

    # Step 3: Query Lookup Fallback
    if not all_candidates and hints.get("title"):
        title = hints["title"]
        artist = hints.get("artist")
        album = hints.get("album")
        tasks = [
            apple_provider.lookup_by_query(title, artist),
            deezer_provider.lookup_by_query(title, artist),
            spotify_provider.lookup_by_query(title, artist),
            mb_provider.lookup_by_query(title, artist, album),
        ]
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
    if best.cover_art_url and (not scan_res.has_cover_art or overwrite):
        for p in providers:
            art_result = await p.fetch_cover_art(best.cover_art_url)
            if art_result:
                art_bytes, art_mime = art_result
                break

    if dry_run:
        console.print(
            f"[dim cyan][DRY-RUN] Would inject {len(best.to_vorbis_comments())} tags "
            f"and {'cover art' if art_bytes else 'no art'}[/dim cyan]"
        )
        return True

    # Step 6: Inject
    inject_metadata(
        file_path,
        best,
        cover_art_bytes=art_bytes,
        cover_art_mime=art_mime,
        overwrite_existing=overwrite,
    )
    console.print(f"[bold green][OK] Injected successfully:[/bold green] {file_path.name}")
    return True


@app.command()
def inject(
    target: Annotated[
        Path,
        typer.Argument(help="Path to a FLAC file or directory containing FLAC files."),
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
    recursive: Annotated[
        bool,
        typer.Option("--recursive/--no-recursive", "-r", help="Recurse into subdirectories."),
    ] = True,
) -> None:
    """Scan and inject standardized Vorbis Comments and cover art into FLAC files."""
    if not target.exists():
        console.print(f"[bold red]Target path does not exist:[/bold red] {target}")
        raise typer.Exit(code=1)

    settings = get_settings()
    glob_pat = "**/*.flac" if recursive else "*.flac"
    flac_files = [target] if target.is_file() else sorted(target.glob(glob_pat))

    if not flac_files:
        console.print("[yellow]No FLAC files found to process.[/yellow]")
        return

    async def _run_all() -> None:
        providers = [
            MusicBrainzProvider(settings=settings),
            AppleITunesProvider(settings=settings),
            DeezerProvider(settings=settings),
            SpotifyProvider(settings=settings),
        ]
        try:
            for file_path in flac_files:
                await _resolve_and_inject_track(
                    file_path,
                    providers,
                    threshold,
                    dry_run,
                    overwrite,
                )
        finally:
            for p in providers:
                await p.close()

    asyncio.run(_run_all())


if __name__ == "__main__":
    app()
