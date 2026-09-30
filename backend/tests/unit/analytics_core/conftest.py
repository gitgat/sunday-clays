"""Synthetic frame builders for Plan 06 unit tests (no DB)."""

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import date, timedelta

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest

from sunday_clays.analytics import frames

RoundSpec = tuple[date, int, int] | Mapping[str, object]
SIM_START = date(2026, 1, 4)


def build_rounds(specs: Sequence[RoundSpec], **defaults: object) -> pd.DataFrame:
    """A frame shaped like `frames.load_rounds`.

    Each spec is an (event_date, shooter_id, score) tuple or a dict of columns.
    Defaults: name_key "s<id>", display_name "Shooter <id>", held True, round_type
    "sporting", status/shooter_status "member", gauge_class None, metrics/weather NaN,
    is_best_round False, round_id 1..n, ordinal 1..k per (event_date, name_key) by
    score desc then input order.
    """
    rows: list[dict[str, object]] = []
    for i, spec in enumerate(specs):
        row: dict[str, object] = (
            {"event_date": spec[0], "shooter_id": spec[1], "score": spec[2]}
            if isinstance(spec, tuple)
            else dict(spec)
        )
        merged = {**defaults, **row}
        sid = merged["shooter_id"]
        merged.setdefault("round_id", i + 1)
        merged.setdefault("name_key", f"s{sid}")
        merged.setdefault("display_name", f"Shooter {sid}")
        merged.setdefault("held", True)
        merged.setdefault("round_type", "sporting")
        merged.setdefault("status", "member")
        merged.setdefault("shooter_status", merged["status"])
        merged.setdefault("gauge_class", None)
        merged.setdefault("is_best_round", False)
        merged["_pos"] = i
        rows.append(merged)
    df = pd.DataFrame(rows)
    if "ordinal" not in df.columns:
        df["ordinal"] = math.nan
    auto = df["ordinal"].isna()
    if auto.any():
        ranked = (
            df.sort_values(["score", "_pos"], ascending=[False, True])
            .groupby(["event_date", "name_key"])
            .cumcount()
            + 1
        )
        df.loc[auto, "ordinal"] = ranked[auto]
    df["ordinal"] = df["ordinal"].astype("int64")
    for column in frames.ROUND_COLUMNS:
        if column not in df.columns:
            df[column] = math.nan
    df["gauge"] = df["gauge_class"].where(df["gauge_class"].notna(), frames.UNSPECIFIED_GAUGE)
    return (
        df.drop(columns="_pos")
        .sort_values(["event_date", "shooter_id", "ordinal"])
        .reset_index(drop=True)
    )


def build_events(specs: Sequence[date | Mapping[str, object]]) -> pd.DataFrame:
    """A frame shaped like `frames.load_events`; defaults: held, scored, NaN metrics."""
    rows: list[dict[str, object]] = []
    for spec in specs:
        row: dict[str, object] = {"event_date": spec} if isinstance(spec, date) else dict(spec)
        row.setdefault("results_complete", True)
        row.setdefault("has_scores", True)
        row.setdefault("has_stations", False)
        row.setdefault("round_type", "sporting")
        row.setdefault("round_type_source", "none")
        row.setdefault("n_rounds", 0)
        row.setdefault("n_shooters", 0)
        rows.append(row)
    df = pd.DataFrame(rows)
    for column in frames.EVENT_COLUMNS:
        if column not in df.columns:
            df[column] = math.nan
    return df[list(frames.EVENT_COLUMNS)].sort_values("event_date").reset_index(drop=True)


def simulate_skill(
    seed: int,
    n_shooters: int,
    n_events: int,
    *,
    drift: float = 0.0,
    obs_var: float = 14.0,
    difficulty_var: float = 4.0,
    attend: float = 0.6,
) -> tuple[pd.DataFrame, npt.NDArray[np.float64]]:
    """Rounds drawn from the C7 skill model itself, plus the final true skills.

    Weekly held events from SIM_START; skills ~ N(30, 49) random-walking with variance
    `drift` per week; one shared N(0, difficulty_var) day effect per event; each shooter
    attends with probability `attend` and shoots one round, rounded and clipped to 0..50.
    Columns: round_id, event_date, shooter_id, name_key, ordinal, score, held. The same
    seed gives the same first k events for any n_events >= k.
    """
    rng = np.random.default_rng(seed)
    skills = rng.normal(30.0, 7.0, n_shooters)
    rows = []
    for t in range(n_events):
        if t:
            skills = skills + rng.normal(0.0, math.sqrt(drift), n_shooters)
        day = rng.normal(0.0, math.sqrt(difficulty_var))
        for s in np.flatnonzero(rng.random(n_shooters) < attend):
            y = np.clip(np.rint(skills[s] + day + rng.normal(0.0, math.sqrt(obs_var))), 0, 50)
            rows.append(
                (
                    len(rows) + 1,
                    SIM_START + timedelta(days=7 * t),
                    int(s) + 1,
                    f"s{s + 1}",
                    1,
                    int(y),
                    True,
                )
            )
    columns = [
        "round_id",
        "event_date",
        "shooter_id",
        "name_key",
        "ordinal",
        "score",
        "held",
    ]
    return pd.DataFrame(rows, columns=columns), skills


@pytest.fixture
def make_rounds() -> Callable[..., pd.DataFrame]:
    return build_rounds


@pytest.fixture
def simulate_skill_rounds() -> Callable[..., tuple[pd.DataFrame, npt.NDArray[np.float64]]]:
    """`simulate_skill`: (rounds, true final skills); calibrate tests take [0]."""
    return simulate_skill


@pytest.fixture
def make_events() -> Callable[..., pd.DataFrame]:
    return build_events
