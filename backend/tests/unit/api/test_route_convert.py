import math

import numpy as np
import pandas as pd
import pytest

from sunday_clays.api.routes._convert import is_missing, opt_float, opt_int, opt_str, rows


@pytest.mark.parametrize("value", [None, pd.NA, math.nan, np.float64("nan")])
def test_missing_values_become_none(value: object) -> None:
    assert is_missing(value)
    assert opt_float(value) is None
    assert opt_int(value) is None
    assert opt_str(value) is None


def test_present_values_become_plain_python() -> None:
    assert opt_float(np.float64(1.5)) == 1.5
    assert type(opt_float(np.int64(2))) is float
    assert opt_int(np.float64(3.0)) == 3
    assert type(opt_int(np.int64(3))) is int
    assert opt_str("x") == "x"
    assert not is_missing(0.0)


def test_rows_are_dicts_keyed_by_column_name() -> None:
    df = pd.DataFrame({"a": [1, 2], 3: ["x", "y"]})
    assert rows(df) == [{"a": 1, "3": "x"}, {"a": 2, "3": "y"}]
    assert rows(df.iloc[0:0]) == []
