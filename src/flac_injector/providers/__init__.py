"""Metadata provider package exports."""

from flac_injector.providers.apple_itunes import AppleITunesProvider
from flac_injector.providers.base import BaseMetadataProvider
from flac_injector.providers.deezer import DeezerProvider
from flac_injector.providers.discogs import DiscogsProvider
from flac_injector.providers.musicbrainz import MusicBrainzProvider
from flac_injector.providers.spotify import SpotifyProvider

__all__ = [
    "AppleITunesProvider",
    "BaseMetadataProvider",
    "DeezerProvider",
    "DiscogsProvider",
    "MusicBrainzProvider",
    "SpotifyProvider",
]
