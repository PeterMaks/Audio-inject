"""Unit and integration tests for async metadata providers with mocked HTTP responses."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from flac_injector.config import Settings
from flac_injector.providers.apple_itunes import AppleITunesProvider
from flac_injector.providers.deezer import DeezerProvider
from flac_injector.providers.discogs import DiscogsProvider
from flac_injector.providers.musicbrainz import MusicBrainzProvider
from flac_injector.providers.songlink import SonglinkProvider
from flac_injector.providers.spotify import SpotifyProvider


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture providing testing settings."""
    return Settings(
        ACOUSTID_API_KEY="test_acoustid_key",
        SPOTIFY_CLIENT_ID="test_spot_id",
        SPOTIFY_CLIENT_SECRET="test_spot_secret",
        DISCOGS_TOKEN="test_discogs_token",
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


@pytest.mark.asyncio
async def test_discogs_lookup_by_query_with_release_detail(mock_settings: Settings) -> None:
    """Test Discogs query search with full release details and artist sanitization."""
    provider = DiscogsProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_search_payload = {
        "results": [
            {
                "id": 999,
                "title": "Aphex Twin - Selected Ambient Works 85-92",
                "year": "1992",
            }
        ]
    }
    mock_detail_payload = {
        "id": 999,
        "title": "Selected Ambient Works 85-92",
        "artists": [{"name": "Aphex Twin (2)"}],
        "year": 1992,
        "released": "1992-02-12",
        "genres": ["Electronic"],
        "styles": ["Ambient", "Techno"],
        "labels": [{"name": "Apollo"}],
        "images": [
            {
                "type": "primary",
                "uri": "https://i.discogs.com/saw8592.jpg",
                "width": 600,
                "height": 600,
            }
        ],
        "identifiers": [
            {"type": "Barcode", "value": "5413356611927"}
        ],
        "tracklist": [
            {
                "position": "1",
                "title": "Xtal",
                "duration": "4:54",
                "extraartists": [
                    {"name": "Richard D. James (2)", "role": "Written-By"}
                ],
            },
            {
                "position": "2",
                "title": "Tha",
                "duration": "9:06",
            },
        ],
    }

    async def mock_request(method: str, url: str, **kwargs):
        if "releases/999" in url:
            return httpx.Response(200, json=mock_detail_payload)
        return httpx.Response(200, json=mock_search_payload)

    with patch.object(provider, "request", side_effect=mock_request):
        results = await provider.lookup_by_query("Xtal", "Aphex Twin")

    assert len(results) == 1
    track = results[0]
    assert track.title == "Xtal"
    assert track.artist == "Aphex Twin"  # Sanitized (2)
    assert track.album == "Selected Ambient Works 85-92"
    assert track.track_number == "1"
    assert track.track_total == "2"
    assert track.composer == "Richard D. James"  # Sanitized (2)
    assert track.genre == ["Electronic", "Ambient", "Techno"]
    assert track.barcode == "5413356611927"
    assert track.label == "Apollo"
    assert track.cover_art_url == "https://i.discogs.com/saw8592.jpg"
    assert track.extra_tags["DISCOGS_RELEASE_ID"] == "999"
    await provider.close()


@pytest.mark.asyncio
async def test_discogs_unconfigured_token() -> None:
    """Test that Discogs returns empty list when no token is configured."""
    empty_settings = Settings(DISCOGS_TOKEN=None)
    provider = DiscogsProvider(settings=empty_settings, rate_limit_delay=0.0)

    results = await provider.lookup_by_query("Xtal")
    assert results == []
    results_isrc = await provider.lookup_by_isrc("USQX91300105")
    assert results_isrc == []
    results_fp = await provider.lookup_by_fingerprint("dummy", 100.0)
    assert results_fp == []
    await provider.close()


@pytest.fixture
def mock_odesli_payload() -> dict:
    """Fixture returning sample Odesli/Songlink cross-platform API payload."""
    return {
        "entityUniqueId": "SPOTIFY_SONG::1jJci4qxiYcOHhQR247rEU",
        "userCountry": "US",
        "pageUrl": "https://song.link/s/1jJci4qxiYcOHhQR247rEU",
        "entitiesByUniqueId": {
            "SPOTIFY_SONG::1jJci4qxiYcOHhQR247rEU": {
                "id": "1jJci4qxiYcOHhQR247rEU",
                "type": "song",
                "title": "One More Time",
                "artistName": "Daft Punk",
                "albumTitle": "Discovery",
                "thumbnailUrl": "https://i.scdn.co/image/ab67616d0000b273sample",
                "thumbnailWidth": 640,
                "thumbnailHeight": 640,
                "apiProvider": "spotify",
                "platforms": ["spotify"],
            },
            "ITUNES_SONG::697195787": {
                "id": "697195787",
                "type": "song",
                "title": "One More Time",
                "artistName": "Daft Punk",
                "albumTitle": "Discovery",
                "thumbnailUrl": "https://is1-ssl.mzstatic.com/image/thumb/Music/100x100bb.jpg",
                "thumbnailWidth": 100,
                "thumbnailHeight": 100,
                "apiProvider": "itunes",
                "platforms": ["appleMusic", "itunes"],
                "isrc": "GBDUW0100055",
            },
        },
        "linksByPlatform": {
            "spotify": {
                "url": "https://open.spotify.com/track/1jJci4qxiYcOHhQR247rEU",
                "entityUniqueId": "SPOTIFY_SONG::1jJci4qxiYcOHhQR247rEU",
            },
            "appleMusic": {
                "url": "https://music.apple.com/us/album/one-more-time/697194953?i=697195787",
                "entityUniqueId": "ITUNES_SONG::697195787",
            },
            "deezer": {
                "url": "https://www.deezer.com/track/3135556",
                "entityUniqueId": "DEEZER_SONG::3135556",
            },
            "youtube": {
                "url": "https://youtube.com/watch?v=FGBhQbmPwH8",
                "entityUniqueId": "YOUTUBE_VIDEO::FGBhQbmPwH8",
            },
            "tidal": {
                "url": "https://tidal.com/browse/track/594191",
                "entityUniqueId": "TIDAL_SONG::594191",
            },
        },
    }


@pytest.mark.asyncio
async def test_songlink_lookup_by_url(mock_settings: Settings, mock_odesli_payload: dict) -> None:
    """Test Songlink resolution via streaming URL."""
    provider = SonglinkProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_resp = httpx.Response(200, json=mock_odesli_payload)
    with patch.object(provider, "request", new=AsyncMock(return_value=mock_resp)):
        results = await provider.lookup_by_url("https://open.spotify.com/track/1jJci4qxiYcOHhQR247rEU")

    assert len(results) == 1
    track = results[0]
    assert track.title == "One More Time"
    assert track.artist == "Daft Punk"
    assert track.album == "Discovery"
    assert track.isrc == "GBDUW0100055"
    assert track.source_provider == "songlink"
    assert track.confidence_score >= 0.90

    # Verify high-res 3000x3000px artwork upgrade from Apple Music entity
    assert track.cover_art_url == "https://is1-ssl.mzstatic.com/image/thumb/Music/3000x3000bb.jpg"
    assert track.cover_art_width == 3000
    assert track.cover_art_height == 3000

    # Verify cross-platform link tagging
    assert track.extra_tags["SONGLINK_URL"] == "https://song.link/s/1jJci4qxiYcOHhQR247rEU"
    assert track.extra_tags["SPOTIFY_URL"] == "https://open.spotify.com/track/1jJci4qxiYcOHhQR247rEU"
    assert track.extra_tags["APPLE_MUSIC_URL"] == "https://music.apple.com/us/album/one-more-time/697194953?i=697195787"
    assert track.extra_tags["DEEZER_URL"] == "https://www.deezer.com/track/3135556"
    assert track.extra_tags["YOUTUBE_URL"] == "https://youtube.com/watch?v=FGBhQbmPwH8"
    assert track.extra_tags["TIDAL_URL"] == "https://tidal.com/browse/track/594191"

    await provider.close()


@pytest.mark.asyncio
async def test_songlink_api_key_configuration(mock_odesli_payload: dict) -> None:
    """Verify that SONGLINK_API_KEY is properly included in request parameters and headers."""
    settings = Settings(SONGLINK_API_KEY="my_secret_odesli_key")
    provider = SonglinkProvider(settings=settings, rate_limit_delay=0.0)

    params = provider._get_request_params("https://song.link/s/123")
    headers = provider._get_request_headers()

    assert params["key"] == "my_secret_odesli_key"
    assert headers["X-Api-Key"] == "my_secret_odesli_key"
    assert headers["Authorization"] == "Bearer my_secret_odesli_key"
    await provider.close()


@pytest.mark.asyncio
async def test_songlink_lookup_by_query_url_passthrough(
    mock_settings: Settings, mock_odesli_payload: dict
) -> None:
    """Verify that when query is a URL, SonglinkProvider routes directly to lookup_by_url."""
    provider = SonglinkProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_resp = httpx.Response(200, json=mock_odesli_payload)
    with patch.object(provider, "request", new=AsyncMock(return_value=mock_resp)):
        results = await provider.lookup_by_query("https://song.link/s/1jJci4qxiYcOHhQR247rEU")

    assert len(results) == 1
    assert results[0].title == "One More Time"
    await provider.close()


@pytest.mark.asyncio
async def test_songlink_lookup_by_query_text_fallback(
    mock_settings: Settings, mock_odesli_payload: dict
) -> None:
    """Verify text queries find streaming URL on Deezer/iTunes and resolve via Songlink."""
    provider = SonglinkProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_deezer_search = {
        "data": [
            {
                "id": 3135556,
                "title": "One More Time",
                "link": "https://www.deezer.com/track/3135556",
            }
        ]
    }

    async def mock_request(method: str, url: str, **kwargs):
        if "api.deezer.com/search" in url:
            return httpx.Response(200, json=mock_deezer_search)
        if "api.song.link" in url or "api.odesli.co" in url:
            return httpx.Response(200, json=mock_odesli_payload)
        return httpx.Response(404)

    with patch.object(provider, "request", side_effect=mock_request):
        results = await provider.lookup_by_query("One More Time", "Daft Punk")

    assert len(results) == 1
    assert results[0].title == "One More Time"
    assert results[0].artist == "Daft Punk"
    await provider.close()


@pytest.mark.asyncio
async def test_songlink_lookup_by_isrc(
    mock_settings: Settings, mock_odesli_payload: dict
) -> None:
    """Verify that ISRC lookup queries Deezer for streaming link and resolves via Songlink."""
    provider = SonglinkProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_deezer_isrc = {
        "id": 3135556,
        "title": "One More Time",
        "link": "https://www.deezer.com/track/3135556",
    }

    async def mock_request(method: str, url: str, **kwargs):
        if "api.deezer.com/track/isrc:" in url:
            return httpx.Response(200, json=mock_deezer_isrc)
        if "api.song.link" in url or "api.odesli.co" in url:
            return httpx.Response(200, json=mock_odesli_payload)
        return httpx.Response(404)

    with patch.object(provider, "request", side_effect=mock_request):
        results = await provider.lookup_by_isrc("GBDUW0100055")

    assert len(results) == 1
    assert results[0].title == "One More Time"
    assert results[0].isrc == "GBDUW0100055"
    await provider.close()


@pytest.mark.asyncio
async def test_songlink_error_handling(mock_settings: Settings) -> None:
    """Verify that HTTP errors or empty responses return empty list safely."""
    provider = SonglinkProvider(settings=mock_settings, rate_limit_delay=0.0)

    mock_err_resp = httpx.Response(401, json={"code": "PUBLIC_API_ACCESS_DEPRECATED"})
    with patch.object(provider, "request", new=AsyncMock(return_value=mock_err_resp)):
        results = await provider.lookup_by_url("https://song.link/s/invalid")
    assert results == []

    # Fingerprint always returns empty
    results_fp = await provider.lookup_by_fingerprint("dummy", 100.0)
    assert results_fp == []
    await provider.close()


