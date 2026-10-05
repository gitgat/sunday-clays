"""Trophy wording for the weekly club email (owner, 2026-10-04).

The email goes to people who never open the site, so a tiered trophy reads as the number reached
("Events Attended - 50"), never the metal. `summary.trophy_title` is untouched: the summary card
keeps its own wording.
"""

from collections.abc import Iterable
from typing import Final

from sunday_clays.analytics.achievements.registry import Tier, Trophy, trophy
from sunday_clays.analytics.summary import LEFT_OUT_TROPHY_CODES

#: A short plain explanation for the one-off trophies whose name alone would not make sense to
#: someone outside the club. Codes missing here (3-Bird Shoot, ...) read fine alone.
ONE_OFF_EXPLANATIONS: Final[dict[str, str]] = {
    "doubleheader": "two rounds in one day",
    "joined_club": "first shot as a guest, now a member",
    "both_disciplines": "shot both a sporting and a super sporting day",
    "comeback": "15 or more targets better than the previous Sunday",
    "above_average_3": "three Sundays in a row above a personal average",
    "welcome_back": "returned after 180 or more days away",
    "new_year": "shot the first Sunday of the year",
    "anniversary_1": "one year since a first Sunday",
    "anniversary_5": "five years since a first Sunday",
    "four_seasons": "shot in winter, spring, summer and fall of one year",
    "perfect_month": "shot every Sunday of a month",
    "sub_gauge": "shot a round with a 20, 28 or .410 gauge",
    "rain": "shot in the rain",
    "cold": "shot on a day colder than 35 F",
    "heat": "shot on a day of 85 F or hotter",
    "wind": "shot on a day with gusts of 20 mph or more",
    "all_weather": "earned the rain, cold, heat and wind trophies",
    "mudder": "broke 40 or more in the rain",
}


def threshold_text(tier: Tier) -> str:
    """1,000 for 1000.0; a fractional threshold keeps its decimals."""
    value = tier.threshold
    return f"{int(value):,}" if value == int(value) else f"{value:,}"


def _item(found: Trophy) -> str:
    if found.tier is not None:
        return f"{found.achievement.name} - {threshold_text(found.tier)}"
    note = ONE_OFF_EXPLANATIONS.get(found.achievement.code)
    return found.achievement.name if note is None else f"{found.achievement.name} ({note})"


def recap_trophy_items(codes: Iterable[str]) -> list[str]:
    """One line item per trophy family: only the highest tier crossed, in first-seen order.

    Unknown codes and D14's four left-out trophies are dropped.
    """
    best: dict[str, Trophy] = {}
    for code in codes:
        found = trophy(code)
        if found is None or found.achievement.code in LEFT_OUT_TROPHY_CODES:
            continue
        family = found.achievement.code
        held = best.get(family)
        if held is None or _level(found) > _level(held):
            best[family] = found
    return [_item(found) for found in best.values()]


def _level(found: Trophy) -> int:
    return 0 if found.tier is None else found.tier.level
