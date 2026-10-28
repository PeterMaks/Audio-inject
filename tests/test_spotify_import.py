"""Unit tests for spotify_import.py (CSV/JSON parsing, similarity matching, gap filling)."""

import json
from pathlib import Path

import pytest

from flac_injector.models import ScanResult
from flac_injector.spotify_import import (
    SpotifyTrackRecord,
    calculate_similarity,
    load_spotify_data,
    match_file_to_spotify,
)

SAMPLE_EXPORTIFY_CSV = """Track URI,Track Name,Album Name,Artist Name(s),Release Date,Duration (ms),Popularity,Explicit,Added By,Added At,Genres,Record Label,Danceability,Energy,Key,Loudness,Mode,Speechiness,Acousticness,Instrumentalness,Liveness,Valence,Tempo,Time Signature
spotify:track:0oCP1Vu9LGVP88atKzOswC,"ambiguous","Linkage Ring","GARNiDELiA",2015-01-21,272480,49,false,,2026-09-25T19:30:14Z,"anime,j-pop,j-rock","Sony Music Labels Inc.",0.441,0.962,0,-2.299,1,0.108,0.142,0.000103,0.317,0.592,178.201,4
spotify:track:1rQaY7Y6YtKHO7aVSWMU6r,"hope to see this dawn","hope to see this dawn","plenka",2026-09-03,184173,46,false,,2026-09-20T12:50:37Z,"witch house,drift phonk,phonk","plenka",0.655,0.861,1,-5.438,1,0.167,0.508,0.954,0.119,0.111,114.997,4
spotify:track:7ttWQnVvBPEVKRV6nPSCjB,"Lamp Light","Wolf Boy","YOUTH 83;A.L.I.S.O.N",2023-03-10,203294,36,false,,2026-09-09T13:47:57Z,"synthwave,chillwave,vaporwave","YOUTH 83 under exclusive license to Amuseio AB",0.451,0.552,8,-12.194,1,0.0357,0.174,0.762,0.153,0.149,84.994,4
spotify:track:2ybKKZwHJ81SpJ2kFHVCUC,"Cash Shit","Cash Carti","Middens",2025-09-10,153513,51,true,,2026-08-29T17:30:14Z,"","Dvpper Digital",0.728,0.626,1,-5.581,1,0.226,0.0564,0.000259,0.129,0.346,161.097,4
"""


def test_load_spotify_data_csv() -> None:
    """Test loading Exportify CSV export data."""
    records = load_spotify_data(SAMPLE_EXPORTIFY_CSV)
    assert len(records) == 4

    rec1 = records[0]
    assert rec1.title == "ambiguous"
    assert rec1.artist == "GARNiDELiA"
    assert rec1.album == "Linkage Ring"
    assert rec1.release_date == "2015-01-21"
    assert rec1.year == "2015"
    assert rec1.duration_ms == 272480
    assert rec1.duration_seconds == 272.48
    assert rec1.explicit is False
    assert rec1.record_label == "Sony Music Labels Inc."
    assert rec1.genres == ["anime", "j-pop", "j-rock"]
    assert rec1.bpm == 178.2
    assert rec1.spotify_id == "0oCP1Vu9LGVP88atKzOswC"
    assert rec1.audio_features.get("danceability") == "0.441"
    assert rec1.audio_features.get("energy") == "0.962"

    rec3 = records[2]
    assert rec3.title == "Lamp Light"
    assert rec3.artists == ["YOUTH 83", "A.L.I.S.O.N"]
    assert rec3.artist == "YOUTH 83, A.L.I.S.O.N"
    assert rec3.album == "Wolf Boy"

    rec4 = records[3]
    assert rec4.title == "Cash Shit"
    assert rec4.explicit is True


def test_load_spotify_data_json_array() -> None:
    """Test loading JSON array of track objects."""
    json_data = [
        {
            "track_name": "Get Lucky",
            "artist_name": "Daft Punk",
            "album_name": "Random Access Memories",
            "duration_ms": 248000,
            "release_date": "2013-05-20",
            "tempo": 116.0,
            "spotify_id": "2Foc5Q5nqNiosCNqttzHof",
            "genres": ["french house", "disco"],
        }
    ]
    records = load_spotify_data(json.dumps(json_data))
    assert len(records) == 1
    assert records[0].title == "Get Lucky"
    assert records[0].artist == "Daft Punk"
    assert records[0].album == "Random Access Memories"
    assert records[0].bpm == 116.0
    assert records[0].spotify_id == "2Foc5Q5nqNiosCNqttzHof"


def test_load_spotify_data_json_api_response() -> None:
    """Test loading Spotify Web API style nested JSON response."""
    api_payload = {
        "tracks": [
            {
                "name": "One More Time",
                "artists": [{"name": "Daft Punk"}],
                "album": {
                    "name": "Discovery",
                    "release_date": "2001-03-12",
                    "images": [{"url": "https://i.scdn.co/image/test123"}],
                },
                "duration_ms": 320357,
                "id": "0DiWol3AO6WpXZgp0goxAV",
                "uri": "spotify:track:0DiWol3AO6WpXZgp0goxAV",
                "explicit": False,
            }
        ]
    }
    records = load_spotify_data(json.dumps(api_payload))
    assert len(records) == 1
    assert records[0].title == "One More Time"
    assert records[0].artist == "Daft Punk"
    assert records[0].album == "Discovery"
    assert records[0].release_date == "2001-03-12"
    assert records[0].cover_art_url == "https://i.scdn.co/image/test123"


def test_calculate_similarity_high_match() -> None:
    """Test calculate_similarity with identical/close metadata and duration."""
    scan = ScanResult(
        path=Path("GARNiDELiA - ambiguous.flac"),
        duration_seconds=272.5,
        sample_rate=44100,
        channels=2,
        bits_per_sample=16,
        existing_tags={"TITLE": ["ambiguous"], "ARTIST": ["GARNiDELiA"]},
        missing_fields=["ALBUM", "DATE"],
        has_cover_art=False,
        is_incomplete=True,
    )
    records = load_spotify_data(SAMPLE_EXPORTIFY_CSV)
    sim = calculate_similarity(scan, {}, records[0])
    assert sim >= 0.90


def test_calculate_similarity_mismatch() -> None:
    """Test calculate_similarity when title and artist are completely different."""
    scan = ScanResult(
        path=Path("Different Artist - Completely Different Song.flac"),
        duration_seconds=120.0,
        sample_rate=44100,
        channels=2,
        bits_per_sample=16,
        existing_tags={"TITLE": ["Completely Different Song"], "ARTIST": ["Different Artist"]},
        missing_fields=[],
        has_cover_art=True,
        is_incomplete=False,
    )
    records = load_spotify_data(SAMPLE_EXPORTIFY_CSV)
    sim = calculate_similarity(scan, {}, records[0])
    assert sim < 0.30


def test_match_file_to_spotify_gap_filling() -> None:
    """Test that gap filling preserves existing tags while filling missing ones."""
    scan = ScanResult(
        path=Path("plenka - hope to see this dawn.flac"),
        duration_seconds=184.2,
        sample_rate=44100,
        channels=2,
        bits_per_sample=16,
        existing_tags={
            "TITLE": ["hope to see this dawn"],
            "ARTIST": ["plenka"],
            "ALBUM": ["Unknown Album"],  # Incomplete gap
        },
        missing_fields=["ALBUM", "DATE", "GENRE", "LABEL", "BPM"],
        has_cover_art=False,
        is_incomplete=True,
    )
    records = load_spotify_data(SAMPLE_EXPORTIFY_CSV)
    match_res = match_file_to_spotify(scan.path, records, threshold=0.70, overwrite=False, scan_result=scan)

    assert match_res.is_match is True
    assert match_res.similarity_score >= 0.85
    assert match_res.metadata_to_inject is not None

    meta = match_res.metadata_to_inject
    # Existing title & artist preserved
    assert meta.title == "hope to see this dawn"
    assert meta.artist == "plenka"
    # Gaps filled
    assert meta.album == "hope to see this dawn"
    assert meta.date == "2026-09-03"
    assert "witch house" in meta.genre
    assert meta.label == "plenka"
    assert meta.bpm == 115.0
    assert meta.extra_tags.get("SPOTIFY_TRACK_ID") == "1rQaY7Y6YtKHO7aVSWMU6r"
    assert "ALBUM" in match_res.missing_gaps_filled
    assert "DATE" in match_res.missing_gaps_filled


def test_match_file_to_spotify_overwrite() -> None:
    """Test that overwrite mode replaces existing tags with Spotify values."""
    scan = ScanResult(
        path=Path("YOUTH 83 - Lamp Light.flac"),
        duration_seconds=203.2,
        sample_rate=44100,
        channels=2,
        bits_per_sample=16,
        existing_tags={
            "TITLE": ["Lamp Light"],
            "ARTIST": ["YOUTH 83"],
            "ALBUM": ["Old Album Name"],
        },
        missing_fields=[],
        has_cover_art=True,
        is_incomplete=False,
    )
    records = load_spotify_data(SAMPLE_EXPORTIFY_CSV)
    # With overwrite=False, existing album should be preserved
    res_no_ow = match_file_to_spotify(scan.path, records, threshold=0.70, overwrite=False, scan_result=scan)
    assert res_no_ow.is_match is True
    assert res_no_ow.metadata_to_inject.album == "Old Album Name"

    # With overwrite=True, existing album should be updated to Spotify's 'Wolf Boy'
    res_ow = match_file_to_spotify(scan.path, records, threshold=0.70, overwrite=True, scan_result=scan)
    assert res_ow.is_match is True
    assert res_ow.metadata_to_inject.album == "Wolf Boy"
    assert "ALBUM" in res_ow.overwritten_tags


def test_cli_match_spotify_dry_run(untagged_flac: Path, tmp_path: Path) -> None:
    """Test CLI match-spotify with --dry-run option."""
    import shutil
    from typer.testing import CliRunner
    from mutagen.flac import FLAC
    from flac_injector.cli import app

    flac_file = tmp_path / "GARNiDELiA - ambiguous.flac"
    shutil.copy(untagged_flac, flac_file)

    audio = FLAC(str(flac_file))
    audio["TITLE"] = ["ambiguous"]
    audio["ARTIST"] = ["GARNiDELiA"]
    audio.save()

    csv_file = tmp_path / "spotify_export.csv"
    csv_file.write_text(SAMPLE_EXPORTIFY_CSV, encoding="utf-8")

    runner = CliRunner(env={"COLUMNS": "300"})
    result = runner.invoke(app, ["match-spotify", str(flac_file), str(csv_file), "--dry-run"])
    assert result.exit_code == 0
    assert "Matched: 1" in result.output
    assert "ambiguous" in result.output


def test_cli_match_spotify_injection(untagged_flac: Path, tmp_path: Path) -> None:
    """Test CLI match-spotify injecting metadata to fill gaps in a FLAC file."""
    import shutil
    from typer.testing import CliRunner
    from mutagen.flac import FLAC
    from flac_injector.cli import app

    flac_file = tmp_path / "track_ambiguous.flac"
    shutil.copy(untagged_flac, flac_file)

    audio = FLAC(str(flac_file))
    audio["TITLE"] = ["ambiguous"]
    audio["ARTIST"] = ["GARNiDELiA"]
    # Missing ALBUM, DATE, GENRE, BPM, LABEL
    audio.save()

    csv_file = tmp_path / "spotify_export.csv"
    csv_file.write_text(SAMPLE_EXPORTIFY_CSV, encoding="utf-8")

    runner = CliRunner(env={"COLUMNS": "300"})
    result = runner.invoke(app, ["match-spotify", str(flac_file), str(csv_file)])
    assert result.exit_code == 0
    assert "Matched: 1" in result.output

    # Inspect the saved file
    updated_audio = FLAC(str(flac_file))
    assert updated_audio["ALBUM"] == ["Linkage Ring"]
    assert updated_audio["DATE"] == ["2015-01-21"]
    assert "anime" in updated_audio["GENRE"]
    assert updated_audio["LABEL"] == ["Sony Music Labels Inc."]
    assert updated_audio["BPM"] == ["178.2"]
    assert updated_audio["SPOTIFY_TRACK_ID"] == ["0oCP1Vu9LGVP88atKzOswC"]


def test_cli_import_spotify_alias(untagged_flac: Path, tmp_path: Path) -> None:
    """Test CLI import-spotify alias works identically."""
    import shutil
    from typer.testing import CliRunner
    from mutagen.flac import FLAC
    from flac_injector.cli import app

    flac_file = tmp_path / "hope to see this dawn.flac"
    shutil.copy(untagged_flac, flac_file)

    audio = FLAC(str(flac_file))
    audio["TITLE"] = ["hope to see this dawn"]
    audio["ARTIST"] = ["plenka"]
    audio.save()

    csv_file = tmp_path / "spotify_export.csv"
    csv_file.write_text(SAMPLE_EXPORTIFY_CSV, encoding="utf-8")

    runner = CliRunner(env={"COLUMNS": "300"})
    result = runner.invoke(app, ["import-spotify", str(flac_file), "--data", str(csv_file), "--dry-run"])
    assert result.exit_code == 0
    assert "Matched: 1" in result.output


@pytest.mark.asyncio
async def test_bridge_run_match_spotify_command(untagged_flac: Path, tmp_path: Path) -> None:
    """Test bridge action run_match_spotify_command."""
    import shutil
    from flac_injector.bridge import run_match_spotify_command
    from mutagen.flac import FLAC

    flac_file = tmp_path / "plenka - hope to see this dawn.flac"
    shutil.copy(untagged_flac, flac_file)

    audio = FLAC(str(flac_file))
    audio["TITLE"] = ["hope to see this dawn"]
    audio["ARTIST"] = ["plenka"]
    audio.save()

    csv_file = tmp_path / "spotify_export.csv"
    csv_file.write_text(SAMPLE_EXPORTIFY_CSV, encoding="utf-8")

    res = await run_match_spotify_command(
        paths=[str(flac_file)],
        data_path=str(csv_file),
        threshold=0.70,
        dry_run=False,
        overwrite=False,
    )
    assert res["processed"] == 1
    assert res["matched"] == 1
    assert res["failed"] == 0
    assert len(res["items"]) == 1
    assert res["items"][0]["status"] == "injected"
    assert res["items"][0]["matched_title"] == "hope to see this dawn"


def test_resolve_album_name_hierarchy() -> None:
    """Test the canonical 3-tier album resolution hierarchy:
    1. Album from data
    2. Single labeled as '{title} - Single'
    3. Both fail -> 'Unknown Album'
    """
    from flac_injector.models import resolve_album_name

    # 1. Album provided by CSV / source
    assert resolve_album_name("Linkage Ring", "ambiguous") == "Linkage Ring"
    assert resolve_album_name("Slow Air", "Black Lagoon") == "Slow Air"

    # 2. Track is a single (or album is 'Single', or album is missing/placeholder)
    assert resolve_album_name("Single", "Dance Alone") == "Dance Alone - Single"
    assert resolve_album_name("- Single", "Dance Alone") == "Dance Alone - Single"
    assert resolve_album_name(None, "Dance Alone") == "Dance Alone - Single"
    assert resolve_album_name("", "Dance Alone") == "Dance Alone - Single"
    assert resolve_album_name("Unknown Album", "Dance Alone") == "Dance Alone - Single"
    assert resolve_album_name("untitled", "Dance Alone") == "Dance Alone - Single"

    # 2b. Standalone single with total_tracks == 1 and album == title
    assert resolve_album_name("Freefall", "Freefall", is_single=True) == "Freefall - Single"
    assert resolve_album_name("Freefall", "Freefall", total_tracks=1) == "Freefall - Single"

    # 2c. Title already ends with ' - Single'
    assert resolve_album_name("Single", "Dance Alone - Single") == "Dance Alone - Single"

    # 3. Both fail (no album, no title)
    assert resolve_album_name(None, None) == "Unknown Album"
    assert resolve_album_name("", "") == "Unknown Album"
    assert resolve_album_name("Unknown Album", "Unknown") == "Unknown Album"
    assert resolve_album_name("none", "untitled") == "Unknown Album"


def test_writer_replaces_placeholder_album_flac(untagged_flac: Path, tmp_path: Path) -> None:
    """Verify inject_metadata overwrites 'Unknown Album' in FLAC even when overwrite_existing=False."""
    import shutil
    from mutagen.flac import FLAC
    from flac_injector.models import TrackMetadata
    from flac_injector.writer import inject_metadata

    flac_file = tmp_path / "flac_placeholder_test.flac"
    shutil.copy(untagged_flac, flac_file)

    # Pre-populate with placeholder album
    audio = FLAC(str(flac_file))
    audio["TITLE"] = ["My Track"]
    audio["ARTIST"] = ["My Artist"]
    audio["ALBUM"] = ["Unknown Album"]
    audio.save()

    # Inject with overwrite_existing=False
    meta = TrackMetadata(
        title="My Track",
        artist="My Artist",
        album="Real Album Name",
    )
    inject_metadata(flac_file, meta, overwrite_existing=False)

    # Read back and verify the placeholder was replaced!
    updated = FLAC(str(flac_file))
    assert updated["ALBUM"] == ["Real Album Name"]


def test_writer_replaces_placeholder_album_mp3(untagged_mp3: Path, tmp_path: Path) -> None:
    """Verify inject_metadata overwrites 'Unknown Album' in MP3 even when overwrite_existing=False."""
    import shutil
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TALB, TIT2, TPE1
    from flac_injector.models import TrackMetadata
    from flac_injector.writer import inject_metadata

    mp3_file = tmp_path / "mp3_placeholder_test.mp3"
    shutil.copy(untagged_mp3, mp3_file)

    audio = MP3(str(mp3_file), ID3=ID3)
    if audio.tags is None:
        audio.add_tags()
    audio.tags.add(TIT2(encoding=3, text=["My Track"]))
    audio.tags.add(TPE1(encoding=3, text=["My Artist"]))
    audio.tags.add(TALB(encoding=3, text=["Unknown Album"]))
    audio.save()

    meta = TrackMetadata(
        title="My Track",
        artist="My Artist",
        album="New Real Album",
    )
    inject_metadata(mp3_file, meta, overwrite_existing=False)

    updated = MP3(str(mp3_file), ID3=ID3)
    assert updated.tags["TALB"].text == ["New Real Album"]


def test_writer_single_label_across_formats(
    untagged_flac: Path, untagged_mp3: Path, tmp_path: Path
) -> None:
    """Verify that a single track is labeled as '{title} - Single' across FLAC and MP3."""
    import shutil
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3
    from flac_injector.models import TrackMetadata
    from flac_injector.writer import inject_metadata

    # 1. FLAC
    flac_target = tmp_path / "single_track.flac"
    shutil.copy(untagged_flac, flac_target)
    flac_meta = TrackMetadata(
        title="Midnight City",
        artist="M83",
        album="Single",  # Marked as single
    )
    inject_metadata(flac_target, flac_meta)
    read_flac = FLAC(str(flac_target))
    assert read_flac["ALBUM"] == ["Midnight City - Single"]

    # 2. MP3
    mp3_target = tmp_path / "single_track.mp3"
    shutil.copy(untagged_mp3, mp3_target)
    mp3_meta = TrackMetadata(
        title="Midnight City",
        artist="M83",
        album="Unknown Album",  # Missing album, title known -> single
    )
    inject_metadata(mp3_target, mp3_meta)
    read_mp3 = MP3(str(mp3_target))
    assert read_mp3.tags["TALB"].text == ["Midnight City - Single"]


def test_writer_unknown_album_fallback_across_formats(
    untagged_flac: Path, untagged_mp3: Path, tmp_path: Path
) -> None:
    """Verify fallback to 'Unknown Album' across FLAC and MP3 when both album and title fail."""
    import shutil
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3
    from flac_injector.models import TrackMetadata
    from flac_injector.writer import inject_metadata

    fallback_meta = TrackMetadata(
        title="unknown",
        artist="unknown artist",
        album="Unknown Album",
    )

    # 1. FLAC
    flac_target = tmp_path / "fallback.flac"
    shutil.copy(untagged_flac, flac_target)
    inject_metadata(flac_target, fallback_meta)
    assert FLAC(str(flac_target))["ALBUM"] == ["Unknown Album"]

    # 2. MP3
    mp3_target = tmp_path / "fallback.mp3"
    shutil.copy(untagged_mp3, mp3_target)
    inject_metadata(mp3_target, fallback_meta)
    assert MP3(str(mp3_target)).tags["TALB"].text == ["Unknown Album"]



