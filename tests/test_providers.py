"""Unit and integration tests for async metadata providers with mocked HTTP responses."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from flac_injector.config import Settings
from flac_injector.providers.apple_itunes import AppleITunesProvider
from flac_injector.providers.deezer import DeezerProvider
from flac_injector.providers.musicbrainz import MusicBrainzProvider
from flac_injector.providers.spotify import SpotifyProvider


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture providing testing settings."""
    return Settings(
        ACOUSTID_API_KEY="test_acoustid_key",
        SPOTIFY_CLIENT_ID="test_spot_id",
        SPOTIFY_CLIENT_SECRET="test_spot_secret",
        RATE_LIMIT_DELAY=0.0,
    )


@pytest.mark.asyncio
async def test_musicbrainz_lookup_by_fingerprint(mock_settings: Settings) -> None:
    """Test AcoustID fingerprint lookup parsing."""
    provider = MusicBrainzProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_acoustid_payload = {
        "status": "ok",
        "results": [
            {
                "id": "acoustid-guid-123",
                "score": 0.98,
                "recordings": [
                    {
                        "id": "mbid-recording-456",
                        "title": "One More Time",
                        "artists": [{"id": "mbid-artist-789", "name": "Daft Punk"}],
                        "releases": [
                            {
                                "id": "mbid-release-001",
                                "title": "Discovery",
                                "date": "2001-03-12",
                                "mediums": [
                                    {"tracks": [{"position": 1}], "track_count": 14}
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_resp = httpx.Response(200, json=mock_acoustid_payload)
    with patch.object(provider, "request", new=AsyncMock(return_value=mock_resp)):
        results = await provider.lookup_by_fingerprint("dummy_fingerprint", 320.0)

    assert len(results) == 1
    track = results[0]
    assert track.title == "One More Time"
    assert track.artist == "Daft Punk"
    assert track.album == "Discovery"
    assert track.acoustid_id == "acoustid-guid-123"
    assert track.musicbrainz_trackid == "mbid-recording-456"
    assert track.musicbrainz_albumid == "mbid-release-001"
    assert track.track_number == "1"
    assert track.track_total == "14"
    assert track.confidence_score == 0.98
    await provider.close()


@pytest.mark.asyncio
async def test_apple_itunes_lookup_and_art_upgrade(mock_settings: Settings) -> None:
    """Test iTunes search parsing and 3000x3000px cover art URL upgrading."""
    provider = AppleITunesProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_itunes_payload = {
        "resultCount": 1,
        "results": [
            {
                "trackName": "Strobe",
                "artistName": "deadmau5",
                "collectionName": "For Lack of a Better Name",
                "trackNumber": 7,
                "trackCount": 10,
                "releaseDate": "2009-09-22T07:00:00Z",
                "primaryGenreName": "Dance",
                "trackExplicitness": "notExplicit",
                "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/100x100bb.jpg",
            }
        ],
    }

    mock_resp = httpx.Response(200, json=mock_itunes_payload)
    with patch.object(provider, "request", new=AsyncMock(return_value=mock_resp)):
        results = await provider.lookup_by_query("Strobe", "deadmau5")

    assert len(results) == 1
    track = results[0]
    assert track.title == "Strobe"
    assert track.artist == "deadmau5"
    assert track.album == "For Lack of a Better Name"
    assert track.track_number == "7"
    assert track.date == "2009-09-22"
    assert track.genre == ["Dance"]
    assert track.explicit is False
    # Check 3000x3000bb URL upgrade
    assert track.cover_art_url == "https://is1-ssl.mzstatic.com/image/thumb/Music/3000x3000bb.jpg"
    assert track.cover_art_width == 3000
    assert track.cover_art_height == 3000
    await provider.close()


@pytest.mark.asyncio
async def test_deezer_lookup_by_isrc(mock_settings: Settings) -> None:
    """Test Deezer ISRC lookup parsing with BPM and uncompressed metadata."""
    provider = DeezerProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_deezer_payload = {
        "id": 3135556,
        "title": "Harder, Better, Faster, Stronger",
        "isrc": "GBDUW0100055",
        "bpm": 123.4,
        "explicit_lyrics": False,
        "track_position": 4,
        "release_date": "2001-03-07",
        "artist": {"name": "Daft Punk"},
        "album": {
            "title": "Discovery",
            "cover_xl": "https://e-cdns-images.dzcdn.net/images/cover/1000x1000-000000-80-0-0.jpg",
        },
    }

    mock_resp = httpx.Response(200, json=mock_deezer_payload)
    with patch.object(provider, "request", new=AsyncMock(return_value=mock_resp)):
        results = await provider.lookup_by_isrc("GBDUW0100055")

    assert len(results) == 1
    track = results[0]
    assert track.title == "Harder, Better, Faster, Stronger"
    assert track.artist == "Daft Punk"
    assert track.album == "Discovery"
    assert track.isrc == "GBDUW0100055"
    assert track.bpm == 123.4
    assert track.explicit is False
    assert track.cover_art_url is not None
    assert "1000x1000" in track.cover_art_url
    await provider.close()


@pytest.mark.asyncio
async def test_spotify_lookup_authenticated(mock_settings: Settings) -> None:
    """Test Spotify API client credentials token caching and track search."""
    provider = SpotifyProvider(settings=mock_settings, rate_limit_delay=0.0)

    # Mock token response
    mock_token_resp = httpx.Response(200, json={"access_token": "mock_tok_abc", "expires_in": 3600})
    mock_search_payload = {
        "tracks": {
            "items": [
                {
                    "name": "Get Lucky",
                    "artists": [{"name": "Daft Punk"}],
                    "album": {
                        "name": "Random Access Memories",
                        "release_date": "2013-05-17",
                        "total_tracks": 13,
                        "images": [{"url": "https://i.scdn.co/image/640.jpg", "width": 640}],
                    },
                    "track_number": 8,
                    "disc_number": 1,
                    "explicit": False,
                    "external_ids": {"isrc": "USQX91300105"},
                }
            ]
        }
    }
    mock_search_resp = httpx.Response(200, json=mock_search_payload)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_token_resp)
    mock_client.request = AsyncMock(return_value=mock_search_resp)

    with patch.object(provider, "get_client", new=AsyncMock(return_value=mock_client)):
        results = await provider.lookup_by_isrc("USQX91300105")

    assert len(results) == 1
    track = results[0]
    assert track.title == "Get Lucky"
    assert track.artist == "Daft Punk"
    assert track.album == "Random Access Memories"
    assert track.track_number == "8"
    assert track.track_total == "13"
    assert track.isrc == "USQX91300105"
    assert track.cover_art_url == "https://i.scdn.co/image/640.jpg"
    await provider.close()


@pytest.mark.asyncio
async def test_spotify_unconfigured_credentials() -> None:
    """Test that Spotify gracefully returns empty list when no credentials exist."""
    empty_settings = Settings(SPOTIFY_CLIENT_ID=None, SPOTIFY_CLIENT_SECRET=None)
    provider = SpotifyProvider(settings=empty_settings)

    results = await provider.lookup_by_query("Test Song")
    assert results == []
    await provider.close()


@pytest.mark.asyncio
async def test_base_fetch_cover_art(mock_settings: Settings) -> None:
    """Test downloading cover art image bytes."""
    provider = AppleITunesProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    mock_resp = httpx.Response(
        200,
        content=mock_image_bytes,
        headers={"content-type": "image/jpeg; charset=utf-8"},
    )

    with patch.object(provider, "request", new=AsyncMock(return_value=mock_resp)):
        art = await provider.fetch_cover_art("https://example.com/art.jpg")

    assert art is not None
    data, mime = art
    assert data == mock_image_bytes
    assert mime == "image/jpeg"
    await provider.close()
