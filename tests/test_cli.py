"""Unit tests for the CLI help flags and command listing."""

import re
from pathlib import Path

from typer.testing import CliRunner

from flac_injector.cli import app


def test_cli_help_short_flag():
    """Verify that '-h' displays the top-level help with all commands."""
    runner = CliRunner()
    result = runner.invoke(app, ["-h"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    # Verify all expected subcommands are listed for the user
    for command in [
        "scan",
        "inspect",
        "fingerprint",
        "inject",
        "match-spotify",
        "import-spotify",
        "convert",
        "clean-art",
    ]:
        assert command in result.output


def test_cli_help_long_flag():
    """Verify that '--help' displays the top-level help with all commands."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "scan" in result.output


def test_cli_subcommand_help_short_flag():
    """Verify that '-h' works on subcommands to show their options."""
    runner = CliRunner()
    result = runner.invoke(app, ["scan", "-h"])
    assert result.exit_code == 0
    assert "target" in result.output
    assert "--recursive" in result.output or "-r" in result.output


def test_cli_inject_no_overwrite_flag(tagged_flac: Path):
    """Verify that inject accepts --no-overwrite without a parsing error."""
    runner = CliRunner()
    result = runner.invoke(app, ["inject", "--help"])
    assert result.exit_code == 0
    clean_output = re.sub(r"\x1b\[[0-9;]*[mK]", "", result.output)
    assert "--overwrite" in clean_output
    assert "--no-overwrite" in clean_output

    exec_result = runner.invoke(app, ["inject", str(tagged_flac), "--no-overwrite", "--dry-run"])
    assert exec_result.exit_code == 0


def test_public_package_exports():
    """Verify that flac_injector exports core library functions."""
    import flac_injector

    expected = [
        "inspect_audio",
        "scan_path",
        "inject_metadata",
        "convert_to_flac",
        "generate_fingerprint",
        "aggregate_candidates",
        "get_settings",
    ]
    for symbol in expected:
        assert hasattr(flac_injector, symbol)

