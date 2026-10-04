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


def make_database_with_a_response_cache(postgres: PostgresContainer, db: str) -> None:
    """<db> holds one real table and the disposable UNLOGGED page cache (Plan 19 D22)."""
    psql(postgres, "test", f"CREATE DATABASE {db}")
    psql(postgres, db, "CREATE TABLE kept (id int); INSERT INTO kept VALUES (1), (2)")
    psql(
        postgres,
        db,
        "CREATE UNLOGGED TABLE response_cache (key text PRIMARY KEY, body text);"
        " INSERT INTO response_cache VALUES ('a', 'x'), ('b', 'y'), ('c', 'z')",
    )
    # Plan 20: ephemeral rate-limit rows (IP fingerprints) are never dumped either; sign-ups stay.
    psql(
        postgres,
        db,
        "CREATE TABLE club_event_attempts (id int PRIMARY KEY, ip text);"
        " INSERT INTO club_event_attempts VALUES (1, 'fp-a'), (2, 'fp-b');"
        " CREATE TABLE club_event_registrations (id int PRIMARY KEY, name text);"
        " INSERT INTO club_event_registrations VALUES (1, 'Amy Ace')",
    )


def run_backup_tool(postgres: PostgresContainer, script: str, db: str) -> tuple[int, str]:
    """backup.sh and verify-restore.sh need python3 only for locking and pruning, and the
    postgres image has none, so a no-op python3 stands in (the tools have their own tests)."""
    prelude = (
        "printf '#!/bin/sh\\nexit 0\\n' > /usr/local/bin/python3\n"
        "chmod +x /usr/local/bin/python3\n"
        "mkdir -p /work/backups\n"
    )
    return run(
        postgres,
        f"{prelude}PGDATABASE={db} BACKUP_DIR=/work/backups /backup/{script}",
    )


def test_backup_leaves_the_response_cache_rows_out_of_the_dump(
    postgres: PostgresContainer,
) -> None:
    """R3: the cache is disposable; its table definition is kept but its data is not dumped.
    Kills: a plain pg_dump (up to 4 GiB of bodies in every daily dump)."""
    make_database_with_a_response_cache(postgres, "dump_cache")
    exit_code, output = run_backup_tool(postgres, "backup.sh --once", "dump_cache")
    assert exit_code == 0, output
    listing = sh(postgres, "pg_restore --list $(ls -t /work/backups/sc-*.dump | head -1)")
    assert "TABLE public response_cache" in listing  # the definition survives
    assert "TABLE DATA public response_cache" not in listing
    assert "TABLE DATA public kept" in listing


def test_backup_leaves_the_club_event_attempts_rows_out_but_keeps_registrations(
    postgres: PostgresContainer,
) -> None:
    """Plan 20: rate-limit rows hold IP fingerprints and are ephemeral; sign-ups stay in backups.
    Kills: dropping --exclude-table-data=club_event_attempts, or excluding registrations too."""
    make_database_with_a_response_cache(postgres, "dump_attempts")
    exit_code, output = run_backup_tool(postgres, "backup.sh --once", "dump_attempts")
    assert exit_code == 0, output
    listing = sh(postgres, "pg_restore --list $(ls -t /work/backups/sc-*.dump | head -1)")
    assert "TABLE public club_event_attempts" in listing
    assert "TABLE DATA public club_event_attempts" not in listing
    assert "TABLE DATA public club_event_registrations" in listing


def test_verify_restore_ignores_the_response_cache_row_count(
    postgres: PostgresContainer,
) -> None:
    """R3: live has 3 cache rows, the restore has 0 (excluded from the dump) and the check must
    still pass, since the worker rewrites that table at any moment. Kills: counting
    response_cache in row_counts."""
    make_database_with_a_response_cache(postgres, "verify_cache")
    exit_code, output = run_backup_tool(postgres, "verify-restore.sh", "verify_cache")
    assert exit_code == 0, output
    assert "tables match" in output


def test_verify_restore_ignores_the_club_event_attempts_row_count(
    postgres: PostgresContainer,
) -> None:
    """Live has 2 attempt rows, the restore has 0, and the check must still pass; registrations
    are still compared. Kills: counting club_event_attempts in row_counts. This test depends on
    the backup.sh --exclude-table-data=club_event_attempts exclusion: without it the restore would
    hold the rows and the skip here would go unproven."""
    make_database_with_a_response_cache(postgres, "verify_attempts")
    exit_code, output = run_backup_tool(postgres, "verify-restore.sh", "verify_attempts")
    assert exit_code == 0, output
    assert "tables match" in output
