"""Launch-switch storage (Plan 19 D1, D4, D26; §5.1, §5.2)."""

import logging
import threading
from datetime import date, datetime

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import record_audit
from sunday_clays.config import Settings
from sunday_clays.domain import features
from sunday_clays.domain.errors import NotFoundError


def _settings(default_on: str = "") -> Settings:
    return Settings.model_construct(features_default_on=default_on, timezone="America/Los_Angeles")


def _put_raw(session: Session, key: str, raw_json: str) -> None:
    session.execute(
        text("INSERT INTO app_state (key, value) VALUES (:k, CAST(:v AS jsonb))"),
        {"k": f"feature.{key}", "v": raw_json},
    )


def test_a_missing_row_is_the_default(session: Session) -> None:
    expected = {f.key: f.default_on for f in features.FEATURES}  # only page_cache defaults on
    assert features.read_switches(session, _settings()) == expected


def test_features_default_on_turns_a_missing_row_on(session: Session) -> None:
    switches = features.read_switches(session, _settings(" pwa, summary_card ,"))
    assert switches["pwa"] is True
    assert switches["summary_card"] is True
    assert switches["link_previews"] is False


def test_a_stored_false_beats_the_default(session: Session) -> None:
    features.set_switch(session, _settings(), "pwa", False)
    assert features.read_switches(session, _settings("pwa"))["pwa"] is False


def test_a_stored_true_is_on(session: Session) -> None:
    out = features.set_switch(session, _settings(), "summary_card", True)
    assert out.enabled is True
    assert features.read_switches(session, _settings())["summary_card"] is True


@pytest.mark.parametrize(
    ("raw", "leaked"),
    [
        ('"on"', '"on"'),
        ('{"enabled": "yes"}', "yes"),
        ("null", "null"),
        ('{"updated_at": "x"}', "updated_at"),
    ],
)
def test_a_corrupt_value_reads_as_off_with_one_warning_naming_the_key_only(
    session: Session, caplog: pytest.LogCaptureFixture, raw: str, leaked: str
) -> None:
    _put_raw(session, "tour_glossary", raw)
    with caplog.at_level(logging.WARNING, logger="sunday_clays.domain.features"):
        switches = features.read_switches(session, _settings("tour_glossary"))
    assert switches["tour_glossary"] is False  # corrupt is off, never the default
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert message == "feature switch tour_glossary has a corrupt value; reading it as off"
    assert leaked not in message
    assert raw not in message


def test_an_unknown_key_is_feature_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError) as caught:
        features.set_switch(session, _settings(), "nope", True)
    assert caught.value.code == "feature_not_found"


def test_updated_at_is_the_database_clock_and_updated_on_the_club_date(session: Session) -> None:
    db_now = session.execute(text("SELECT now()")).scalar_one()
    out = features.set_switch(session, _settings(), "pwa", True)
    assert out.updated_at == db_now  # now() is the transaction start, so equal, not "close"


def test_updated_on_converts_utc_to_the_club_timezone(session: Session) -> None:
    _put_raw(session, "pwa", '{"enabled": true, "updated_at": "2026-10-03T05:30:00+00:00"}')
    (row,) = [s for s in features.list_switches(session, _settings()) if s.key == "pwa"]
    assert row.updated_at == datetime.fromisoformat("2026-10-03T05:30:00+00:00")
    assert row.updated_on == date(2026, 10, 2)  # 22:30 on Oct 2 in Los Angeles


def test_list_switches_reports_never_changed_rows_with_no_dates(session: Session) -> None:
    rows = features.list_switches(session, _settings())
    assert [r.key for r in rows] == [f.key for f in features.FEATURES]
    assert all(r.updated_at is None and r.updated_on is None for r in rows)


def test_two_concurrent_puts_of_one_key_are_last_writer_wins(committed_engine: Engine) -> None:
    """§5.2: two admins flip one key at once. The row ends with exactly one writer's value and its
    database now(), that writer is the one that committed last, and both flips are audited.

    "Last" is read from the database, not from thread scheduling: each writer takes
    clock_timestamp() after its upsert, inside its transaction. The second upsert blocks on the
    first writer's row lock until that commit, so its clock_timestamp() is the later one."""
    barrier = threading.Barrier(2)
    writes: list[tuple[bool, datetime, datetime]] = []
    lock = threading.Lock()

    def flip(enabled: bool) -> None:
        with Session(committed_engine) as s:
            started = s.execute(text("SELECT now()")).scalar_one()
            barrier.wait()
            out = features.set_switch(s, _settings(), "weekly_recap", enabled)
            # the two calls PUT /api/admin/features/{key} makes, in its one transaction
            details = {"key": out.key, "enabled": out.enabled}
            record_audit(s, None, "admin", "feature_switch", details)
            wrote_at = s.execute(text("SELECT clock_timestamp()")).scalar_one()
            s.commit()
            with lock:
                writes.append((enabled, started, wrote_at))

    threads = [threading.Thread(target=flip, args=(v,)) for v in (True, False)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(writes) == 2
    last_enabled, last_started, _ = max(writes, key=lambda w: w[2])
    with Session(committed_engine) as s:
        (row,) = [r for r in features.list_switches(s, _settings()) if r.key == "weekly_recap"]
        audits = (
            s.execute(
                text("SELECT details FROM audit_log WHERE action = 'feature_switch' ORDER BY id")
            )
            .scalars()
            .all()
        )
    assert row.enabled is last_enabled
    assert row.updated_at == last_started  # the later transaction's database now()
    assert sorted(a["enabled"] for a in audits) == [False, True]  # exactly two audit rows
    assert {a["key"] for a in audits} == {"weekly_recap"}


def _cache_rows(session: Session) -> int:
    return int(session.execute(text("SELECT count(*) FROM response_cache")).scalar_one())


def _put_cache_row(session: Session, key: str) -> None:
    session.execute(
        text(
            "INSERT INTO response_cache"
            " (key, data_version, local_date, app_version, role, route, body)"
            " VALUES (:k, 1, '2026-10-02', 'dev', 'viewer', '/api/meta', '{}')"
        ),
        {"k": key},
    )


def test_page_cache_missing_row_is_on_whatever_the_default_list_says(session: Session) -> None:
    assert features.read_switches(session, _settings(""))["page_cache"] is True
    assert features.read_switches(session, _settings("pwa"))["page_cache"] is True


def test_page_cache_on_needs_the_switch_and_the_setting(session: Session) -> None:
    on = Settings.model_construct(features_default_on="", timezone="UTC", page_cache_enabled=True)
    off = Settings.model_construct(features_default_on="", timezone="UTC", page_cache_enabled=False)
    assert features.page_cache_on(session, on) is True
    assert features.page_cache_on(session, off) is False
    features.set_switch(session, on, "page_cache", False)
    assert features.page_cache_on(session, on) is False


def test_page_cache_on_reads_only_its_own_row(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Kills reading every switch (read_switches) on the request path: a corrupt row of another
    feature must not log a warning on every cached GET."""
    on = Settings.model_construct(features_default_on="", timezone="UTC", page_cache_enabled=True)
    _put_raw(session, "tour_glossary", '"on"')
    with caplog.at_level(logging.WARNING, logger="sunday_clays.domain.features"):
        assert features.page_cache_on(session, on) is True
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []
    _put_raw(session, "page_cache", '"on"')
    assert features.infrastructure_switch_on(session, "page_cache") is False  # corrupt is off


@pytest.mark.parametrize("enabled", [False, True])
def test_flipping_page_cache_purges_the_table_either_way(session: Session, enabled: bool) -> None:
    _put_cache_row(session, "a")
    _put_cache_row(session, "b")
    session.execute(
        text("INSERT INTO app_state (key, value) VALUES (:k, '{\"data_version\": 1}'::jsonb)"),
        {"k": features.LAST_WARM_KEY},
    )
    features.set_switch(session, _settings(), "page_cache", enabled)
    assert _cache_rows(session) == 0
    last_warm = session.execute(
        text("SELECT count(*) FROM app_state WHERE key = :k"), {"k": features.LAST_WARM_KEY}
    ).scalar_one()
    assert last_warm == (0 if enabled else 1)  # "on" also forgets the last warm-up


def test_flipping_a_feature_leaves_the_cache_alone(session: Session) -> None:
    _put_cache_row(session, "a")
    features.set_switch(session, _settings(), "summary_card", True)
    assert _cache_rows(session) == 1


def test_infrastructure_switch_on_refuses_a_launch_switch(session: Session) -> None:
    with pytest.raises(ValueError, match="not an infrastructure switch"):
        features.infrastructure_switch_on(session, "pwa")
