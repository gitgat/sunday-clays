"""The thrown-out world: frames carry the flags and load_thrown_out reads them (T2a)."""

from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.domain.thrown_out import ThrownOut
from sunday_clays.models import Event, Round, Shooter

THROWN_OUT_SUNDAY = date(2026, 10, 25)


def test_the_thrown_out_world_has_ten_sundays_and_credited_scores(
    fx_thrown_out_session: Session,
) -> None:  # guard: world shape
    s = fx_thrown_out_session
    assert s.execute(select(func.count()).select_from(Event)).scalar_one() == 10
    assert s.execute(select(func.count()).select_from(Round)).scalar_one() == 90
    day = s.execute(
        select(Shooter.display_name, Round.score)
        .join(Shooter, Shooter.id == Round.shooter_id)
        .where(Round.event_date == THROWN_OUT_SUNDAY)
        .order_by(Round.score.desc(), Shooter.display_name)
    ).all()
    assert [tuple(r) for r in day] == [
        ("Hadley, Ike", 43),
        ("Abernathy, Preston", 41),
        ("Birch, Lou", 39),
        ("Kim, Pat", 37),
        ("Crane, Dot", 35),
        ("Kaplan, Noel", 35),
        ("Ellis, Fay", 31),
        ("Ace, Amy", 29),
        ("Devlin, Sid", 27),
    ]
    assert s.execute(text("SELECT count(*) FROM event_weather")).scalar_one() == 10


def test_frames_carry_the_thrown_out_flags(fx_thrown_out_session: Session) -> None:
    s = fx_thrown_out_session
    rounds = frames.load_rounds(s)
    assert rounds["stats_excluded"].dtype == bool
    assert int(rounds["stats_excluded"].sum()) == 9
    assert set(rounds.loc[rounds["stats_excluded"], "event_date"]) == {THROWN_OUT_SUNDAY}
    for loader in (frames.load_events, frames.load_calendar):
        ev = loader(s)
        assert ev.loc[ev["stats_excluded"], "event_date"].tolist() == [THROWN_OUT_SUNDAY]
    hits = frames.load_station_hits(s)
    assert len(hits) == 630
    assert hits["dropped"].dtype == bool
    dropped = hits[hits["dropped"]]
    assert set(zip(dropped["event_date"], dropped["station_label"], strict=True)) == {
        (THROWN_OUT_SUNDAY, "11")
    }
    assert dropped["hits"].tolist() == [7] * 9


def test_load_thrown_out_reads_the_auto_drop(fx_thrown_out_session: Session) -> None:
    assert frames.load_thrown_out(fx_thrown_out_session) == {
        THROWN_OUT_SUNDAY: (ThrownOut("11", 7, True, "auto"),)
    }


def test_load_thrown_out_reads_overrides_and_sunday_level_flags(
    fx_thrown_out_session: Session,
) -> None:
    s = fx_thrown_out_session
    s.execute(
        text(
            "UPDATE station_layouts SET dropped = true, dropped_source = 'override'"
            " WHERE event_date = '2026-10-11' AND station_label = '5'"
        )
    )
    s.execute(
        text(
            "UPDATE events SET stats_excluded = true"
            " WHERE event_date IN ('2026-10-11', '2026-10-18')"
        )
    )
    clear_cache()
    got = frames.load_thrown_out(s)
    assert got[date(2026, 10, 11)] == (ThrownOut("5", 7, False, "override"),)
    assert got[date(2026, 10, 18)] == (ThrownOut(None, None, False, "override"),)
    assert list(got) == [date(2026, 10, 11), date(2026, 10, 18), THROWN_OUT_SUNDAY]
