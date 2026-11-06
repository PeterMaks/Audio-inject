"""Unit tests for the CLI help flags and command listing."""

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

