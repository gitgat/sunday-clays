"""Only findings about the previewed Sunday are listed; older ones are only counted."""

import datetime as dt
from types import SimpleNamespace
from typing import Any, cast

from sunday_clays.domain.schemas import FindingOut
from sunday_clays.mcp.writes import _split_findings

DAY = dt.date(2026, 10, 4)


def _finding(
    code: str, day: dt.date | None, name: str | None = None, message: str = "m"
) -> FindingOut:
    return FindingOut(code=code, severity="warning", message=message, event_date=day, name=name)


def _preview(*findings: FindingOut) -> Any:
    return cast(Any, SimpleNamespace(findings=list(findings)))


def test_a_finding_for_the_previewed_date_is_listed_and_the_rest_counted() -> None:
    here = _finding("station_score_mismatch", DAY, "Testshooter, Alpha", "this Sunday")
    older = _finding("station_score_mismatch", dt.date(2026, 9, 27))
    undated = _finding("something_general", None)

    mine, other = _split_findings(DAY, [_preview(here, older), _preview(undated)], [])

    assert mine == [here]
    assert other == 2


def test_an_unmatched_station_name_that_is_a_new_shooter_is_dropped() -> None:
    new = _finding("station_name_unmatched", DAY, "Testshooter, Alpha")
    known = _finding("station_name_unmatched", DAY, "Someone, Else")

    mine, other = _split_findings(DAY, [_preview(new, known)], ["Testshooter, Alpha"])

    assert mine == [known]
    assert other == 0
