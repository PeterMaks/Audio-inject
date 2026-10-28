"""Unit tests for spotify_import.py (CSV/JSON parsing, similarity matching, gap filling)."""

import json
import shutil
from pathlib import Path

import pytest
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from flac_injector.models import ScanResult, TrackMetadata
from flac_injector.spotify_import import (
    SpotifyTrackRecord,
    calculate_similarity,
    load_spotify_data,
    match_file_to_spotify,
)
from flac_injector.writer import inject_metadata

# rest of file unchanged
