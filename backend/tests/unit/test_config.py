import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from sunday_clays.config import ConfigError, Settings, database_url_from_env, get_settings


def test_defaults_match_the_contract(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    defaulted = {
        "APP_VERSION",
        "MAX_UPLOAD_BYTES",
        "WEATHER_ENABLED",
        "TIMEZONE",
        "CLUB_LAT",
        "CLUB_LON",
        "LOGIN_MAX_FAILURES",
        "LOGIN_WINDOW_MINUTES",
        "COOKIE_SECURE",  # settings_env sets it; the default is what this test checks
    }
    for key in list(os.environ):  # any case: Settings matches env names case-insensitively
        if key.upper() in defaulted:
            monkeypatch.delenv(key)

    settings = get_settings()

    assert settings.club_lat == 45.3525
    assert settings.club_lon == -122.8082
    assert settings.timezone == "America/Los_Angeles"
    assert settings.max_upload_bytes == 10_485_760
    assert settings.weather_enabled is True
    assert settings.login_max_failures == 10
    assert settings.login_window_minutes == 15
    assert settings.cookie_secure is True
    assert settings.app_version == "dev"


def test_env_overrides_defaults(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEATHER_ENABLED", "false")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1000")

    settings = get_settings()

    assert settings.weather_enabled is False
    assert settings.max_upload_bytes == 1000
    assert settings.cookie_secure is False


def test_secret_file_contents_are_stripped(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret_file = tmp_path / "session_secret"
    secret_file.write_text("  " + "f" * 40 + "\n", encoding="utf-8")
    monkeypatch.delenv("SESSION_SECRET")
    monkeypatch.setenv("SESSION_SECRET_FILE", str(secret_file))

    assert get_settings().session_secret.get_secret_value() == "f" * 40


def test_setting_both_var_and_file_names_both_and_hides_the_value(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret_file = tmp_path / "db_url"
    secret_file.write_text("postgresql+psycopg://from-file", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:hunter2@db/x")
    monkeypatch.setenv("DATABASE_URL_FILE", str(secret_file))

    with pytest.raises(ConfigError) as excinfo:
        Settings()

    message = str(excinfo.value)
    assert "DATABASE_URL" in message
    assert "DATABASE_URL_FILE" in message
    assert str(secret_file) in message
    assert "hunter2" not in message
    assert "from-file" not in message


def test_file_variable_pointing_to_missing_file_is_an_error(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "nope"
    monkeypatch.delenv("ADMIN_PASSWORD_HASH")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH_FILE", str(missing))

    with pytest.raises(ConfigError, match="ADMIN_PASSWORD_HASH_FILE") as excinfo:
        Settings()

    assert str(missing) in str(excinfo.value)


def test_file_variable_pointing_to_empty_file_is_an_error(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blank = tmp_path / "blank"
    blank.write_text(" \n", encoding="utf-8")
    monkeypatch.delenv("VIEWER_PASSWORD_HASH")
    monkeypatch.setenv("VIEWER_PASSWORD_HASH_FILE", str(blank))

    with pytest.raises(ConfigError, match="empty") as excinfo:
        Settings()

    assert "VIEWER_PASSWORD_HASH_FILE" in str(excinfo.value)


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a mode-000 file")
def test_file_variable_pointing_to_unreadable_file_is_an_error(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    locked = tmp_path / "session_secret"
    locked.write_text("hunter2" * 8, encoding="utf-8")
    locked.chmod(0)
    monkeypatch.delenv("SESSION_SECRET")
    monkeypatch.setenv("SESSION_SECRET_FILE", str(locked))

    with pytest.raises(ConfigError) as excinfo:
        Settings()

    assert str(excinfo.value) == f"SESSION_SECRET_FILE is not readable: {locked}"
    assert excinfo.value.__context__ is None


def test_file_variable_pointing_to_non_utf8_file_is_an_error_that_hides_the_bytes(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = tmp_path / "admin_password_hash"
    binary.write_bytes(b"\xff\xfe$argon2id$hunter2")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH_FILE", str(binary))

    with pytest.raises(ConfigError) as excinfo:
        Settings()

    assert str(excinfo.value) == f"ADMIN_PASSWORD_HASH_FILE is not readable: {binary}"
    # A chained UnicodeDecodeError would carry the file's raw bytes into any traceback.
    assert excinfo.value.__context__ is None


def test_short_session_secret_is_rejected_without_echoing_it(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "short-secret-hunter2")

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    assert "session_secret" in str(excinfo.value)
    assert "hunter2" not in str(excinfo.value)


def test_non_argon2id_password_hash_is_rejected_without_echoing_it(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    bcrypt_hash = "$2b$12$abcdefghijklmnopqrstuvhunter2hunter2hunter2hunter2hu"
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", bcrypt_hash)

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    assert "admin_password_hash" in str(excinfo.value)
    assert "hunter2" not in str(excinfo.value)


def test_missing_secret_is_rejected(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SESSION_SECRET")

    with pytest.raises(ValidationError, match="session_secret"):
        Settings()


def test_database_url_from_env_needs_no_other_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in ("DATABASE_URL", "SESSION_SECRET", "VIEWER_PASSWORD_HASH", "ADMIN_PASSWORD_HASH"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(f"{name}_FILE", raising=False)
    url_file = tmp_path / "database_url"
    url_file.write_text("postgresql+psycopg://sunday:pw@db:5432/sunday_clays\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL_FILE", str(url_file))

    assert database_url_from_env() == "postgresql+psycopg://sunday:pw@db:5432/sunday_clays"


def test_database_url_from_env_without_any_source_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_FILE", raising=False)

    with pytest.raises(ConfigError, match="DATABASE_URL"):
        database_url_from_env()
