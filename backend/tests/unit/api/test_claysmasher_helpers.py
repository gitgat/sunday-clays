"""Pure helpers behind the ClaySmasher export (spec 2026-10-01 §4.1); no database."""

from datetime import UTC, date, datetime, timedelta, timezone

from sunday_clays.api.routes._claysmasher import (
    TARGETS_PER_ROUND,
    day_ordinals,
    latest,
    round_key,
    rule_stamps,
    station_orders,
)

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)


def test_round_key_is_the_natural_key_joined_by_colons() -> None:
    assert round_key(D1, "doe jane", 2) == "2026-09-06:doe jane:2"
    # one-token identity keys carry their own @date; ':' never occurs in a key
    assert round_key(D1, "jane@2026-09-06", 1) == "2026-09-06:jane@2026-09-06:1"


def test_station_orders_rank_labels_in_station_order() -> None:
    assert station_orders(["10", "7A", "4", "7", "8", "4"]) == {
        "4": 1,
        "7": 2,
        "7A": 3,
        "8": 4,
        "10": 5,
    }
    assert station_orders([]) == {}


def test_day_ordinals_number_a_shooters_rounds_per_day() -> None:
    keys = [(D1, "doe jane", 1), (D1, "doe j", 1), (D1, "doe jane", 2), (D2, "doe jane", 1)]
    assert day_ordinals(keys) == {
        (D1, "doe j", 1): 1,
        (D1, "doe jane", 1): 2,
        (D1, "doe jane", 2): 3,
        (D2, "doe jane", 1): 1,
    }


def test_latest_is_the_newest_present_stamp_in_utc() -> None:
    pdt = timezone(timedelta(hours=-7))
    a = datetime(2026, 9, 7, 2, 11, tzinfo=UTC)
    b = datetime(2026, 9, 6, 20, 0, tzinfo=pdt)  # 2026-09-07T03:00Z
    newest = latest(a, None, b)
    assert newest == datetime(2026, 9, 7, 3, 0, tzinfo=UTC)
    assert newest is not None
    assert newest.tzinfo is UTC
    assert latest(None, None) is None
    assert latest() is None


def test_rule_stamps_key_round_rules_by_round_and_round_type_rules_by_day() -> None:
    t1 = datetime(2026, 9, 8, tzinfo=UTC)
    t2 = t1 + timedelta(days=1)
    rules = [
        (
            "score_override",
            {"event_date": "2026-09-06", "name_key": "doe jane", "ordinal": 1, "score": 45},
            t2,
        ),
        ("hide_round", {"event_date": "2026-09-06", "name_key": "doe jane", "ordinal": 1}, t1),
        ("round_type_override", {"event_date": "2026-09-06", "round_type": "super_sporting"}, t1),
        ("round_type_override", {"event_date": "2026-09-06", "round_type": "sporting"}, t2),
    ]
    by_round, by_day = rule_stamps(rules)
    assert by_round == {(D1, "doe jane", 1): t2}
    assert by_day == {D1: t2}


def test_a_round_without_stations_counts_fifty_targets() -> None:
    assert TARGETS_PER_ROUND == 50
