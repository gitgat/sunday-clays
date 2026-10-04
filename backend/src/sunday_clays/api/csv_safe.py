import re

_FORMULA = re.compile(r"[=+\-@\t\r]|\s+[=+\-@]")


def csv_safe(cell: str) -> str:
    """Prefix `'` when a spreadsheet could read the cell as a formula: it starts with `=`, `+`,
    `-`, `@`, a tab or a carriage return, or with whitespace followed by one of `= + - @`."""
    return f"'{cell}" if _FORMULA.match(cell) else cell
