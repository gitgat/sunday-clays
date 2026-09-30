import importlib.util
from collections.abc import Callable
from datetime import date, timedelta

import pandas as pd

from sunday_clays.analytics import frames
from sunday_clays.analytics.leaderboards import active_shooter_ids

AS_OF = date(2026, 9, 27)


def test_activity_window_is_364_days(make_rounds: Callable[..., pd.DataFrame]) -> None:
    old = [(AS_OF - timedelta(days=700 + 7 * k), s, 30) for s in (1, 2) for k in range(5)]
    edge = [(AS_OF - timedelta(days=364), 1, 30), (AS_OF - timedelta(days=357), 2, 30)]
    rounds = make_rounds([*old, *edge])
    assert active_shooter_ids(rounds, AS_OF) == {2}


def test_five_rounds_count_even_on_four_sundays(make_rounds: Callable[..., pd.DataFrame]) -> None:
    # Shooter 1 has 5 rounds on 4 dates (a doubleheader) and is active; shooter 2 has 4 rounds.
    dates = [AS_OF - timedelta(days=7 * k) for k in range(4)]
    specs = [(d, 1, 30) for d in dates] + [(dates[0], 1, 25)] + [(d, 2, 30) for d in dates]
    assert active_shooter_ids(make_rounds(specs), AS_OF) == {1}


def test_later_rounds_are_ignored(make_rounds: Callable[..., pd.DataFrame]) -> None:
    dates = [AS_OF + timedelta(days=7 * k) for k in range(1, 6)]
    assert active_shooter_ids(make_rounds([(d, 1, 30) for d in dates]), AS_OF) == set()


def test_future_rounds_do_not_change_the_active_set(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    past = [AS_OF - timedelta(days=7 * k) for k in range(5)]
    past4 = past[:4]
    future = AS_OF + timedelta(days=7)
    specs = [(d, 1, 30) for d in past]  # active with 5 past rounds
    specs += [(d, 2, 30) for d in past4] + [(future, 2, 30)]  # 4 past + 1 future: not active
    base = active_shooter_ids(make_rounds(specs), AS_OF)
    assert base == {1}
    more = [*specs, (future, 1, 30)]
    assert active_shooter_ids(make_rounds(more), AS_OF) == {1}


def test_empty_live_tables_give_no_active_shooters() -> None:
    # What the loaders return on an empty DB: the columns, no rows, object dtypes.
    rounds = pd.DataFrame(columns=list(frames.ROUND_COLUMNS))
    assert active_shooter_ids(rounds, AS_OF) == set()


def test_rating_classes_module_is_gone() -> None:
    assert importlib.util.find_spec("sunday_clays.analytics.classes") is None
