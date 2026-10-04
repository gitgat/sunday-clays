"""The club-event rules without a database (Plan 20 §5.3, D9, D11, D21, D22)."""

import json
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sunday_clays.domain import club_events as rules
from sunday_clays.domain.club_events import QueueRow
from sunday_clays.domain.errors import ConflictError, DomainError

ADMIT_CASES = (
    Path(__file__).resolve().parents[4] / "frontend/src/features/club-events/admitCases.json"
)
LA = "America/Los_Angeles"
T0 = datetime(2026, 10, 2, 18, 0, tzinfo=UTC)


def going(rid: int, guests: int = 0, at: datetime = T0) -> QueueRow:
    return QueueRow(id=rid, status="going", guests=guests, queue_at=at)


def waiting(rid: int, guests: int = 0, at: datetime = T0) -> QueueRow:
    return QueueRow(id=rid, status="waitlist", guests=guests, queue_at=at)


def _cases() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], json.loads(ADMIT_CASES.read_text()))


# --- the queue (D9) ------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _cases(), ids=lambda c: str(c["case"]))
def test_admit_matches_the_shared_cases(case: dict[str, Any]) -> None:
    queue: list[QueueRow] = []
    if case["going_spots"]:
        queue.append(going(1, guests=case["going_spots"] - 1))
    queue += [waiting(10 + n) for n in range(case["waitlist"])]
    assert rules.admit(queue, case["capacity"], case["new_spots"]) == case["expect"]


def test_an_empty_queue_admits_and_spots_count_guests() -> None:
    assert rules.admit([], 1, 1) == "going"
    assert rules.admit([], 1, 2) == "waitlist"
    assert rules.going_spots([going(1, guests=2), waiting(2, guests=5)]) == 3


def test_newcomer_never_jumps_the_waitlist() -> None:
    queue = [going(1), waiting(2, guests=3)]
    assert rules.admit(queue, 5, 1) == "waitlist"  # 1 + 1 fits, but someone is waiting


def test_promotion_stops_at_first_party_that_does_not_fit() -> None:
    queue = [going(1, guests=1), waiting(2, guests=3), waiting(3)]
    assert rules.promotions(queue, 4) == []  # 2 open; the +3 party needs 4; the solo waits


def test_promotion_takes_parties_in_order_while_they_fit() -> None:
    queue = [going(1, guests=1), waiting(2, guests=3), waiting(3), waiting(4)]
    assert rules.promotions(queue, 7) == [2, 3]


def test_no_capacity_promotes_the_whole_waitlist() -> None:
    assert rules.promotions([going(1), waiting(3), waiting(2)], None) == [2, 3]


def test_queue_orders_by_id_not_queue_at() -> None:
    later_id_earlier_time = waiting(5, at=T0)
    earlier_id_later_time = waiting(4, at=T0 + timedelta(hours=1))
    queue = [later_id_earlier_time, earlier_id_later_time]
    assert rules.promotions(queue, 1) == [4]
    assert rules.waitlist_positions(queue) == {4: 1, 5: 2}


# --- names (§5.3.5) ------------------------------------------------------------------------------


def test_signup_key_ignores_order_commas_case_and_spaces() -> None:
    assert rules.signup_key("Ike Hadley") == "hadley ike"
    assert rules.signup_key("Hadley, Ike") == "hadley ike"
    assert rules.signup_key(" hadley  IKE ") == "hadley ike"
    assert rules.signup_key(rules.signup_key("Ike Hadley")) == "hadley ike"


def test_typed_name_is_cleaned_and_keyed() -> None:
    assert rules.typed_name("Dana Quill") == ("Dana Quill", "dana quill")
    assert rules.typed_name("  Quill,  Dana ") == ("Quill, Dana", "dana quill")


@pytest.mark.parametrize(
    ("raw", "code"),
    [("Dana", "name_needs_last"), ("D", "bad_name"), ("Q" * 30 + " " + "D" * 30, "bad_name")],
)
def test_typed_name_refusals(raw: str, code: str) -> None:
    with pytest.raises(DomainError) as info:
        rules.typed_name(raw)
    assert info.value.code == code
    assert info.value.status_code == 400


def test_a_one_word_name_asks_for_the_last_name() -> None:
    with pytest.raises(DomainError, match="Add your last name too"):
        rules.typed_name("Dana")


# --- emails (§5.3.6, D11) ------------------------------------------------------------------------


def test_normalise_email_strips_folds_and_lowercases() -> None:
    assert rules.normalise_email(" Dana.Quill@Example.COM ") == "dana.quill@example.com"
    fullwidth = "\uff44\uff41\uff4e\uff41@example.com"  # escaped: ruff RUF001
    assert rules.normalise_email(fullwidth) == "dana@example.com"  # NFKC
    assert rules.normalise_email("ü@x.de") == "ü@x.de"
    longest = "a" * 64 + "@" + "b" * 186 + ".de"
    assert len(longest) == 254
    assert rules.normalise_email(longest) == longest


@pytest.mark.parametrize(
    "raw",
    ["a@b", "a b@c.de", "", "@example.com", "a" * 65 + "@x.de", "a" * 64 + "@" + "b" * 187 + ".de"],
)
def test_normalise_email_refusals(raw: str) -> None:
    with pytest.raises(DomainError) as info:
        rules.normalise_email(raw)
    assert (info.value.code, info.value.message) == (
        "bad_email",
        "Enter an email like name@example.com.",
    )


def test_email_match_non_ascii(settings_env: None) -> None:
    assert rules.email_matches("ü@x.de", "Ü@x.de") is True
    assert rules.email_matches("u@x.de", "ü@x.de") is False  # a plain mismatch, no TypeError


def test_email_match_nothing_stored(settings_env: None) -> None:
    assert rules.email_matches(None, "dana.quill@example.com") is False
    assert rules.email_matches("", "dana.quill@example.com") is False


def test_email_match_folds_the_typed_email(settings_env: None) -> None:
    assert rules.email_matches("dana.quill@example.com", "  DANA.Quill@example.com ") is True
    assert rules.email_matches("dana.quill@example.com", "dana.quil@example.com") is False
    assert rules.email_matches("dana.quill@example.com", "not an email") is False


def test_tokens_match_only_their_own_hash() -> None:
    token, digest = rules.new_token()
    assert len(digest) == 64
    assert digest == rules.token_hash(token)
    assert rules.token_matches(digest, token) is True
    assert rules.token_matches(digest, token + "x") is False
    assert rules.token_matches(None, token) is False
    assert rules.token_matches(rules.DUMMY_TOKEN_HASH, "\ud800") is False  # lone surrogate


# --- club time (D21) -----------------------------------------------------------------------------


def test_a_spring_forward_time_is_refused() -> None:
    with pytest.raises(DomainError) as info:
        rules.local_to_utc("2026-03-08T02:30", LA)
    assert info.value.code == "bad_local_time"
    assert info.value.message == "That time doesn't exist on that day (clocks spring forward)."


def test_a_fall_back_time_takes_the_first_occurrence() -> None:
    assert rules.local_to_utc("2026-11-01T01:30", LA) == datetime(2026, 11, 1, 8, 30, tzinfo=UTC)


@pytest.mark.parametrize("raw", ["2026-10-17", "2026-10-17T25:00", "tomorrow", "2026-02-30T10:00"])
def test_an_unreadable_local_time_is_refused(raw: str) -> None:
    with pytest.raises(DomainError, match="Enter a date and a time"):
        rules.local_to_utc(raw, LA)


def test_local_parts_are_club_time() -> None:
    late = datetime(2026, 10, 18, 6, 30, tzinfo=UTC)  # Sat Oct 17, 23:30 in Los Angeles
    assert rules.local_to_utc("2026-10-17T23:30", LA) == late
    assert rules.local_parts(late, LA) == (date(2026, 10, 17), "23:30")


def test_event_state() -> None:
    starts, deadline = T0 + timedelta(days=2), T0 + timedelta(days=1)
    assert rules.event_state(T0, starts, deadline, None) == "open"
    assert rules.event_state(deadline, starts, deadline, None) == "closed"
    assert rules.event_state(starts, starts, deadline, None) == "started"
    assert rules.event_state(T0, starts, deadline, T0) == "cancelled"
    assert rules.event_state(starts, starts, deadline, T0) == "cancelled"


def test_a_late_evening_event_is_upcoming_until_club_midnight() -> None:
    starts = datetime(2026, 10, 18, 6, 30, tzinfo=UTC)  # Sat Oct 17, 23:30 LA
    assert rules.is_upcoming(starts, datetime(2026, 10, 18, 6, 45, tzinfo=UTC), LA) is True
    assert rules.is_upcoming(starts, datetime(2026, 10, 18, 7, 1, tzinfo=UTC), LA) is False


# --- guests (§5.3.4) -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("guests", "allow", "most", "message"),
    [
        (1, False, 0, "This event is members only, no guests."),
        (3, True, 2, "Bring up to 2 guests."),
        (-1, True, 2, "Bring up to 2 guests."),
    ],
)
def test_check_guests_refusals(guests: int, allow: bool, most: int, message: str) -> None:
    with pytest.raises(DomainError) as info:
        rules.check_guests(guests, allow, most)
    assert (info.value.code, info.value.message) == ("bad_guests", message)


def test_check_guests_accepts_the_rule() -> None:
    rules.check_guests(0, False, 0)
    rules.check_guests(2, True, 2)


# --- the database-error scrubber (D22.2) ---------------------------------------------------------


class _Diag:
    def __init__(self, constraint_name: str | None) -> None:
        self.constraint_name = constraint_name


class _PgError(Exception):
    def __init__(self, constraint_name: str | None) -> None:
        super().__init__("DETAIL: Failing row contains (7, Dana Quill, dana.quill@example.com)")
        self.diag = _Diag(constraint_name)


def _violation(constraint_name: str | None) -> IntegrityError:
    return IntegrityError(
        "INSERT INTO club_event_registrations …",
        {"registrant_email": "dana.quill@example.com"},
        _PgError(constraint_name),
    )


class _FakeSession:
    def __init__(self, fail_on_flush: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.fail_on_flush = fail_on_flush

    def flush(self) -> None:
        self.calls.append("flush")
        if self.fail_on_flush is not None:
            raise self.fail_on_flush

    def rollback(self) -> None:
        self.calls.append("rollback")


def test_a_check_violation_becomes_a_bare_500_that_logs_no_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    fake = _FakeSession()
    with (
        pytest.raises(rules.InternalError) as info,
        rules.scrub_db_errors(cast(Session, fake)),
    ):
        raise _violation("ck_club_event_registrations_inactive_scrubbed")
    assert (info.value.status_code, info.value.code) == (500, "internal")
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__ is True
    assert fake.calls == ["rollback"]
    assert "IntegrityError" in caplog.text
    assert "ck_club_event_registrations_inactive_scrubbed" in caplog.text
    assert "@" not in caplog.text
    assert "Quill" not in caplog.text


def test_a_duplicate_index_violation_is_already_signed_up() -> None:
    fake = _FakeSession()
    with (
        pytest.raises(ConflictError) as info,
        rules.scrub_db_errors(cast(Session, fake), "Dana Quill is already on the list."),
    ):
        raise _violation("uq_club_event_registrations_name")
    assert (info.value.code, info.value.message) == (
        "already_signed_up",
        "Dana Quill is already on the list.",
    )


def test_a_violation_at_the_closing_flush_is_caught_too() -> None:
    fake = _FakeSession(fail_on_flush=_violation(None))
    with pytest.raises(rules.InternalError), rules.scrub_db_errors(cast(Session, fake)):
        pass
    assert fake.calls == ["flush", "rollback"]


def test_a_clean_block_just_flushes() -> None:
    fake = _FakeSession()
    with rules.scrub_db_errors(cast(Session, fake)):
        pass
    assert fake.calls == ["flush"]


def test_the_retention_constants_are_the_about_page_numbers() -> None:
    assert (rules.ROSTER_RETENTION_DAYS, rules.CONTACT_RETENTION_DAYS) == (30, 730)
    assert (rules.CANCEL_FAIL_PER_REGISTRATION, rules.MAX_ACTIVE_PER_EVENT) == (5, 200)
