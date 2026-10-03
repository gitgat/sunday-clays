"""The only input of a preview (Plan 19 D10): a facts object with no name field."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.api.routes._convert import opt_int, opt_str, rows
from sunday_clays.domain.round_type import RoundType

PreviewKind = Literal["generic", "sunday", "special"]


@dataclass(frozen=True)
class PreviewFacts:
    kind: PreviewKind
    event_date: date | None = None
    n_shooters: int | None = None
    round_type: RoundType | None = None
    label: str | None = None  # a special shoot's admin-entered label (<= 60 characters)


GENERIC: Final = PreviewFacts("generic")
_EVENT_PATH: Final = re.compile(r"^events/(\d{4}-\d{2}-\d{2})/?$")


def page_path(path: str) -> str:
    """The SPA path without its leading slash and without a leading ``l/`` share prefix."""
    stripped = path.lstrip("/")
    return stripped.removeprefix("l/") if stripped.startswith("l/") else stripped


def facts_for_path(session: Session, path: str, switch_on: bool) -> PreviewFacts:
    """``events/<date>`` of a calendar Sunday (switch on) is a Sunday or special; all else generic.

    Profiles, Year in Review, unknown paths and unknown or malformed dates are generic, so a
    preview never confirms that a person exists (§3.1.5).
    """
    if not switch_on:
        return GENERIC
    match = _EVENT_PATH.match(page_path(path))
    if match is None:
        return GENERIC
    try:
        day = date.fromisoformat(match.group(1))
    except ValueError:
        return GENERIC
    calendar = frames.load_calendar(session)
    found = calendar.loc[calendar["event_date"] == day]
    if found.empty:
        return GENERIC
    row = rows(found)[0]
    count = int(row["n_shooters"]) if bool(row["has_scores"]) else opt_int(row["head_count"])
    round_type = RoundType(str(row["round_type"]))
    if row["kind"] == frames.EVENT_KIND_SPECIAL:
        return PreviewFacts("special", day, count, round_type, opt_str(row["label"]))
    return PreviewFacts("sunday", day, count, round_type)
