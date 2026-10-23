"""Unit tests for the flac_injector bridge module."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from flac_injector.bridge import (
    dispatch_command,
    get_env_settings,
    run_health_check,
    run_inspect_command,
    run_scan_command,
    save_env_settings,
)


def test_health_check():
    """Verify system health inspection returns expected structure."""
    health = run_health_check()
    assert "python_version" in health
    assert "in_venv" in health
    assert "ffmpeg" in health
    assert "fpcalc" in health
    assert "env_status" in health
    assert "songlink_configured" in health["env_status"]
    assert isinstance(health["ffmpeg"]["available"], bool)
    assert isinstance(health["env_status"]["confidence_threshold"], float)


def test_scan_command(tagged_flac: Path, untagged_flac: Path):
    """Verify scan command serializes audio tracks and detects completeness."""
    res = run_scan_command([str(tagged_flac), str(untagged_flac)])
    assert res["total"] == 2
    assert res["complete"] == 1
    assert res["incomplete"] == 1
    assert "FLAC" in res["format_counts"]

    tagged_item = next(item for item in res["items"] if item["filename"] == tagged_flac.name)
    assert tagged_item["has_cover_art"] is True
    assert tagged_item["is_incomplete"] is False
    assert tagged_item["existing_tags"]["TITLE"] == ["Strobe"]


def test_inspect_command(tagged_flac: Path):
    """Verify inspect command retrieves Vorbis comments and base64 cover art."""
    res = run_inspect_command(str(tagged_flac), include_art_base64=True)
    assert res["filename"] == tagged_flac.name
    assert res["has_cover_art"] is True
    assert "cover_art_data_url" in res
    assert res["cover_art_data_url"].startswith("data:image/jpeg;base64,")
    assert res["existing_tags"]["ARTIST"] == ["deadmau5"]


def test_env_settings_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify get_env_settings and save_env_settings modify .env safely."""
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("CONFIDENCE_THRESHOLD=0.75\n", encoding="utf-8")

    current = get_env_settings()
    assert current["CONFIDENCE_THRESHOLD"] == 0.75
    assert "SONGLINK_API_KEY" in current

    updated = save_env_settings({
        "CONFIDENCE_THRESHOLD": 0.85,
        "SPOTIFY_CLIENT_ID": "test_id_123",
        "SONGLINK_API_KEY": "test_songlink_key_456",
    })
    assert updated["CONFIDENCE_THRESHOLD"] == 0.85
    assert updated["SPOTIFY_CLIENT_ID"] == "test_id_123"
    assert updated["SONGLINK_API_KEY"] == "test_songlink_key_456"

    saved_text = env_file.read_text(encoding="utf-8")
    assert "CONFIDENCE_THRESHOLD=0.85" in saved_text
    assert "SPOTIFY_CLIENT_ID=test_id_123" in saved_text
    assert "SONGLINK_API_KEY=test_songlink_key_456" in saved_text


@pytest.mark.asyncio
async def test_dispatch_command_stdout(tagged_flac: Path, capsys: pytest.CaptureFixture):
    """Verify dispatch_command prints NDJSON results to stdout."""
    await dispatch_command("inspect", {"path": str(tagged_flac), "include_art_base64": False})
    captured = capsys.readouterr()
    lines = [json.loads(line) for line in captured.out.strip().splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["type"] == "result"
    assert lines[0]["action"] == "inspect"
    assert lines[0]["data"]["filename"] == tagged_flac.name


def test_bridge_cli_execution(tagged_flac: Path):
    """Verify running python -m flac_injector.bridge via subprocess."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "flac_injector.bridge",
            "inspect",
            json.dumps({"path": str(tagged_flac), "include_art_base64": False}),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    lines = [json.loads(line) for line in proc.stdout.strip().splitlines() if line.strip()]
    assert len(lines) >= 1
    assert lines[-1]["type"] == "result"
    assert lines[-1]["action"] == "inspect"
    assert lines[-1]["data"]["filename"] == tagged_flac.name


def test_bridge_stdin_execution(tagged_flac: Path):
    """Verify running python -m flac_injector.bridge with '-' reading parameters via stdin."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "flac_injector.bridge",
            "inspect",
            "-",
        ],
        input=json.dumps({"path": str(tagged_flac), "include_art_base64": False}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    lines = [json.loads(line) for line in proc.stdout.strip().splitlines() if line.strip()]
    assert len(lines) >= 1
    assert lines[-1]["type"] == "result"
    assert lines[-1]["action"] == "inspect"
    assert lines[-1]["data"]["filename"] == tagged_flac.name

