"""The fx_special world is the fx world plus one special Sunday (Plan 17 Task 2)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.models import Event, Round, Shooter

SPECIAL = date(2026, 9, 20)


def test_the_special_world_is_the_fixture_world_plus_one_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    base = {tuple(r) for r in fx_session.execute(select(Event.event_date, Event.n_rounds))}
    special = fx_special_session.execute(
        select(Event.event_date, Event.n_rounds, Event.kind, Event.label, Event.target_total)
    ).all()

    assert {(d, n) for d, n, kind, _, _ in special if kind == "regular"} == base
    assert [tuple(r) for r in special if r[2] == "special"] == [
        (SPECIAL, 5, "special", "3-Bird Shoot", 60)
    ]
    scores = fx_special_session.execute(
        select(Shooter.display_name, Round.score)
        .join(Shooter, Shooter.id == Round.shooter_id)
        .where(Round.event_date == SPECIAL)
        .order_by(Round.score.desc())
    ).all()
    assert [tuple(r) for r in scores] == [
        ("Hadley, Ike", 55),
        ("Kaplan, Noel", 51),
        ("Devlin, Sid", 48),
        ("Abernathy, Preston", 44),
        ("Kim, Pat", 39),
    ]
