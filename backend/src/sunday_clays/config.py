"""Application settings (C2): env vars plus ``<NAME>_FILE`` Docker secrets, read lazily."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import SecretStr, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

SECRET_FIELDS = ("database_url", "session_secret", "viewer_password_hash", "admin_password_hash")
ARGON2ID_PREFIX = "$argon2id$"
MIN_SESSION_SECRET_BYTES = 32


class ConfigError(RuntimeError):
    """Startup configuration error; the message names variables and paths, never values."""


def read_secret_env(name: str) -> str | None:
    """Value of env ``NAME``, or the stripped contents of the file named by ``NAME_FILE``."""
    env = {key.upper(): value for key, value in os.environ.items()}
    var = name.upper()
    file_var = f"{var}_FILE"
    file_path = env.get(file_var)
    if file_path is None:
        return env.get(var)
    if var in env:
        raise ConfigError(f"Set only one of {var} and {file_var} (file: {file_path})")
    path = Path(file_path)
    if not path.is_file():
        raise ConfigError(f"{file_var} points to a missing file: {file_path}")
    value: str | None
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        value = None  # raised below, outside the handler: a decode error holds the raw bytes
    if value is None:
        raise ConfigError(f"{file_var} is not readable: {file_path}")
    if not value:
        raise ConfigError(f"{file_var} points to an empty file: {file_path}")
    return value


class SecretEnvSource(PydanticBaseSettingsSource):
    """Resolves every secret field from ``NAME`` or ``NAME_FILE`` (C2)."""

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return read_secret_env(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for name in SECRET_FIELDS:
            value, key, _ = self.get_field_value(self.settings_cls.model_fields[name], name)
            if value is not None:
                values[key] = value
        return values


class Settings(BaseSettings):
    # hide_input_in_errors only hides str(error): ValidationError.errors() still carries the
    # input values, so never serialize a Settings failure's .errors(); use include_input=False.
    model_config = SettingsConfigDict(hide_input_in_errors=True, extra="ignore")

    database_url: SecretStr
    session_secret: SecretStr
    viewer_password_hash: SecretStr
    admin_password_hash: SecretStr
    club_lat: float = 45.3525
    club_lon: float = -122.8082
    timezone: str = "America/Los_Angeles"
    max_upload_bytes: int = 10_485_760
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    app_version: str = "dev"
    weather_enabled: bool = True
    login_max_failures: int = 10
    login_window_minutes: int = 15
    page_view_limit: int = 600  # Plan 16: page-view beacons per IP per 10 minutes
    cookie_secure: bool = True

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, SecretEnvSource(settings_cls), env_settings)

    @field_validator("session_secret")
    @classmethod
    def _session_secret_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < MIN_SESSION_SECRET_BYTES:
            raise ValueError(f"session_secret must be at least {MIN_SESSION_SECRET_BYTES} bytes")
        return value

    @field_validator("viewer_password_hash", "admin_password_hash")
    @classmethod
    def _argon2id_hash(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(ARGON2ID_PREFIX):
            raise ValueError(f"password hashes must start with {ARGON2ID_PREFIX}")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def database_url_from_env() -> str:
    """The database URL from ``DATABASE_URL`` / ``DATABASE_URL_FILE`` only (migrations/env.py)."""
    value = read_secret_env("database_url")
    if value is None:
        raise ConfigError("Set DATABASE_URL or DATABASE_URL_FILE")
    return value
