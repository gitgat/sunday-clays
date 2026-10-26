"""Trophy station entries carry the thrown-out flag and the context leaves them out (T4c)."""

from sqlalchemy.orm import Session

from sunday_clays.analytics.achievements.context import (
    STATION_COLUMNS,
    build_context,
    load_station_entries,
)


def test_trophy_entries_carry_the_flag_and_the_context_leaves_it_out(
    fx_thrown_out_session: Session,
) -> None:
    entries = load_station_entries(fx_thrown_out_session)
    assert list(entries.columns) == list(STATION_COLUMNS)
    assert entries["dropped"].dtype == bool
    assert int(entries["dropped"].sum()) == 9
    ctx = build_context(fx_thrown_out_session)
    assert len(ctx.station_hits) == 621
    assert not ctx.station_hits["dropped"].any()
