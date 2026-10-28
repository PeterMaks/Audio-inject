"""flac-meta-injector: Production-grade FLAC metadata and cover art injector."""

from flac_injector.models import PLACEHOLDER_TAG_VALUES, resolve_album_name
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

# Execute headless subprocess patch on package initialization
install_windows_headless_subprocess_patch()

__version__ = "0.1.0"

__all__ = [
    "MatchResult",
    "PLACEHOLDER_TAG_VALUES",
    "SpotifyTrackRecord",
    "calculate_similarity",
    "get_windows_headless_kwargs",
    "install_windows_headless_subprocess_patch",
    "load_spotify_data",
    "match_file_to_spotify",
    "resolve_album_name",
    "__version__",
]
