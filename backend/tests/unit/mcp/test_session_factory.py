"""The mcp service mounts only the database URL, never the login secrets."""

import pytest
from sqlalchemy.orm import sessionmaker

from sunday_clays import db
from sunday_clays.mcp import server


@pytest.fixture(autouse=True)
def _only_the_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "SESSION_SECRET",
        "SESSION_SECRET_FILE",
        "VIEWER_PASSWORD_HASH",
        "VIEWER_PASSWORD_HASH_FILE",
        "ADMIN_PASSWORD_HASH",
        "ADMIN_PASSWORD_HASH_FILE",
        "DATABASE_URL_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/none")
    from sunday_clays.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(db, "SessionFactory", sessionmaker())


def test_factory_configures_with_only_the_database_url() -> None:
    with server.default_session_factory() as session:
        assert session.get_bind() is not None
