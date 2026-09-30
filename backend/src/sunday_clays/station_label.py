"""Station labels such as "7" and "7A" (owner rule 2026-09-29).

A station has a label (the text on the course sheet) and a number, its sort key: the leading
digits, so 7 for "7A". Stations sort by (number, suffix): 4, 5, 6, 7, 7A, 8. Pure module.
"""

import re

_LABEL = re.compile(r"^(\d{1,2})([A-Z]?)$")


def parse_label(value: object) -> str | None:
    """The label of a station cell, or None when the cell is not a station label.

    Accepts ints, integral floats, numeric text and labels such as "7A" (trimmed, upper-cased).
    Station 0, bools and anything else (a "Total" header, a decimal) are not labels.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        value = int(value)
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip().upper()
        if re.fullmatch(r"\d+\.0+", text):  # numeric text from a spreadsheet: "7.0"
            text = text.split(".", 1)[0]
    else:
        return None
    match = _LABEL.match(text)
    if match is None:
        return None
    number = int(match.group(1))
    if number < 1:
        return None
    return f"{number}{match.group(2)}"


def label_number(label: str) -> int:
    """The sort integer of a valid label: its leading digits."""
    match = _LABEL.match(label)
    if match is None:
        raise ValueError(f"{label!r} is not a station label")
    return int(match.group(1))


def label_sort_key(label: str) -> tuple[int, str]:
    """Sort key giving 4, 5, 6, 7, 7A, 8 order."""
    match = _LABEL.match(label)
    if match is None:
        raise ValueError(f"{label!r} is not a station label")
    return (int(match.group(1)), match.group(2))


def label_rank(label: str) -> int:
    """One integer that sorts labels in station order: 7 -> 700, 7A -> 701, 8 -> 800."""
    number, suffix = label_sort_key(label)
    return number * 100 + (ord(suffix) - ord("A") + 1 if suffix else 0)
