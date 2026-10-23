"""Configuration and environment settings for flac-meta-injector."""

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API credentials
    acoustid_api_key: str | None = Field(default=None, alias="ACOUSTID_API_KEY")
    spotify_client_id: str | None = Field(default=None, alias="SPOTIFY_CLIENT_ID")
    spotify_client_secret: str | None = Field(default=None, alias="SPOTIFY_CLIENT_SECRET")
    discogs_token: str | None = Field(default=None, alias="DISCOGS_TOKEN")
    songlink_api_key: str | None = Field(default=None, alias="SONGLINK_API_KEY")

    @model_validator(mode="before")
    @classmethod
    def resolve_songlink_key(cls, data: Any) -> Any:
        import os
        if isinstance(data, dict):
            if not data.get("SONGLINK_API_KEY") and data.get("ODESLI_API_KEY"):
                data["SONGLINK_API_KEY"] = data["ODESLI_API_KEY"]
            elif not data.get("SONGLINK_API_KEY") and os.environ.get("ODESLI_API_KEY"):
                data["SONGLINK_API_KEY"] = os.environ.get("ODESLI_API_KEY")
        return data

    # MusicBrainz compliant User-Agent
    musicbrainz_user_agent: str = Field(
        default="flac-meta-injector/0.1.0 (contact: info@example.com)",
        alias="MUSICBRAINZ_USER_AGENT",
    )

    # Operational settings
    rate_limit_delay: float = Field(default=1.0, alias="RATE_LIMIT_DELAY")
    cover_art_min_resolution: int = Field(default=600, alias="COVER_ART_MIN_RESOLUTION")
    confidence_threshold: float = Field(default=0.70, alias="CONFIDENCE_THRESHOLD")
    request_timeout: float = Field(default=15.0, alias="REQUEST_TIMEOUT")
    fpcalc_path: str = Field(default="fpcalc", alias="FPCALC_PATH")


def get_settings(env_file: Path | str | None = None) -> Settings:
    """Load settings optionally specifying a custom .env file path."""
    if env_file:
        return Settings(_env_file=env_file)
    cwd_env = Path(".env")
    if cwd_env.is_file():
        return Settings(_env_file=cwd_env)
    repo_env = Path(__file__).resolve().parents[2] / ".env"
    if repo_env.is_file():
        return Settings(_env_file=repo_env)
    return Settings()
