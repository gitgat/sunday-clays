"""restore.sh against a real postgres:17 (client tools included), with backend/backup mounted.

A restore over a live database must replace the whole public schema (tables a newer migration
added must not survive) and must be all or nothing: a dump that fails part-way leaves the
database exactly as it was.
"""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.community.postgres import PostgresContainer

BACKUP_DIR = Path(__file__).resolve().parents[3] / "backup"
RESTORE_ENV = {
    "PGHOST": "127.0.0.1",
    "PGUSER": "test",
    "PGDATABASE": "test",
    "POSTGRES_PASSWORD_FILE": "/work/db_password",
}


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresContainer]:
    with pytest.MonkeyPatch.context() as mp:
        if sys.platform == "darwin" and "TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE" not in os.environ:
            mp.setenv("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", "/var/run/docker.sock")
        container = PostgresContainer("postgres:17").with_volume_mapping(
            str(BACKUP_DIR), "/backup", "ro"
        )
        with container as started:
            sh(started, "mkdir -p /work && printf test > /work/db_password")
            yield started


def run(postgres: PostgresContainer, script: str) -> tuple[int, str]:
    """Runs a bash script in the container with the restore env: (exit code, stdout+stderr)."""
    exit_code, output = postgres.get_wrapped_container().exec_run(
        ["bash", "-c", f"set -euo pipefail\n{script}"], environment=RESTORE_ENV
    )
    return exit_code, output.decode()


def sh(postgres: PostgresContainer, script: str) -> str:
    exit_code, output = run(postgres, script)
    assert exit_code == 0, output
    return output


def psql(postgres: PostgresContainer, db: str, sql: str) -> str:
    return sh(
        postgres, f'PGPASSWORD=test psql -X -At -v ON_ERROR_STOP=1 -d {db} -c "{sql}"'
    ).strip()


def make_database_with_a_dump(postgres: PostgresContainer, db: str) -> str:
    """Creates <db> (tables big and kept), dumps it, then drifts: a row and a table are added."""
    psql(postgres, "test", f"CREATE DATABASE {db}")
    psql(postgres, db, "CREATE TABLE kept (id int); INSERT INTO kept VALUES (1), (2)")
    psql(
        postgres,
        db,
        "CREATE TABLE big AS SELECT g AS id, md5(g::text) AS v FROM generate_series(1, 50000) g",
    )
    dump = f"/work/{db}.dump"
    sh(postgres, f"PGPASSWORD=test pg_dump --format=custom --file={dump} -d {db}")
    psql(postgres, db, "INSERT INTO kept VALUES (3); CREATE TABLE added_later (id int)")
    return dump


def tables(postgres: PostgresContainer, db: str) -> list[str]:
    sql = (
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1"
    )
    return psql(postgres, db, sql).split()


def public_schema(postgres: PostgresContainer, db: str) -> str:
    sql = "SELECT nspowner::regrole, nspacl FROM pg_namespace WHERE nspname = 'public'"
    return psql(postgres, db, sql)


def test_restore_replaces_the_whole_public_schema(postgres: PostgresContainer) -> None:
    dump = make_database_with_a_dump(postgres, "replace_me")

    sh(postgres, f"/backup/restore.sh {dump} replace_me")

    assert tables(postgres, "replace_me") == ["big", "kept"]
    assert psql(postgres, "replace_me", "SELECT count(*) FROM kept") == "2"
    psql(postgres, "test", "CREATE DATABASE fresh")
    assert public_schema(postgres, "replace_me") == public_schema(postgres, "fresh")


def test_a_dump_that_fails_part_way_leaves_the_database_as_it_was(
    postgres: PostgresContainer,
) -> None:
    dump = make_database_with_a_dump(postgres, "keep_me")
    cut = f"{dump}.cut"  # the table of contents still lists; the last table's data is cut off
    sh(postgres, f"head -c $(( $(stat -c %s {dump}) - 4096 )) {dump} > {cut}")
    sh(postgres, f"pg_restore --list {cut} > /dev/null")

    exit_code, output = run(postgres, f"/backup/restore.sh {cut} keep_me")

    assert exit_code != 0, output
    assert tables(postgres, "keep_me") == ["added_later", "big", "kept"], output
    assert psql(postgres, "keep_me", "SELECT count(*) FROM kept") == "3", output
