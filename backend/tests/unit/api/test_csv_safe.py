"""csv_safe (Plan 20 §5.5): a spreadsheet must never read a cell as a formula."""

import pytest

from sunday_clays.api.csv_safe import csv_safe


@pytest.mark.parametrize(
    "cell",
    ["=1+1", "+1", "-2", "@SUM(A1)", "\tx", "\rx", "  =1+1", "\t-2", " @x", '=HYPERLINK("x")'],
)
def test_formula_like_cells_get_a_leading_quote(cell: str) -> None:
    assert csv_safe(cell) == "'" + cell


@pytest.mark.parametrize("cell", ["Ike", "1-2", "a=b", "", "Hadley, Ike", "dana.quill@example.com"])
def test_plain_cells_are_unchanged(cell: str) -> None:
    assert csv_safe(cell) == cell
