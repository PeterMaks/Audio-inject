"""flac-meta-injector: Lossless FLAC/MP3 metadata and cover art injector."""

from flac_injector.config import Settings, get_settings
from flac_injector.converter import ConversionError, convert_to_flac, find_ffmpeg_binary
from flac_injector.fingerprint import generate_fingerprint, parse_filename_metadata
from flac_injector.merger import aggregate_candidates
from flac_injector.models import PLACEHOLDER_TAG_VALUES, TrackMetadata, resolve_album_name
from flac_injector.scanner import ScanResult, inspect_audio, scan_path
from flac_injector.spotify_import import (
    MatchResult,
    SpotifyTrackRecord,
    calculate_similarity,
    load_spotify_data,
    match_file_to_spotify,
)
from flac_injector.subprocess_patch import (
    get_windows_headless_kwargs,
    install_windows_headless_subprocess_patch,
)
from flac_injector.writer import inject_metadata

# Execute headless subprocess patch on package initialization
install_windows_headless_subprocess_patch()

__version__ = "0.1.0"

__all__ = [
    "ConversionError",
    "MatchResult",
    "PLACEHOLDER_TAG_VALUES",
    "ScanResult",
    "Settings",
    "SpotifyTrackRecord",
    "TrackMetadata",
    "aggregate_candidates",
    "calculate_similarity",
    "convert_to_flac",
    "find_ffmpeg_binary",
    "generate_fingerprint",
    "get_settings",
    "get_windows_headless_kwargs",
    "inject_metadata",
    "inspect_audio",
    "install_windows_headless_subprocess_patch",
    "load_spotify_data",
    "match_file_to_spotify",
    "parse_filename_metadata",
    "resolve_album_name",
    "scan_path",
    "__version__",
]
