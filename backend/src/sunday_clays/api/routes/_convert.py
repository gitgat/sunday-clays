"""pandas/numpy scalars -> plain Python for read routes (skipped by discovery)."""

import math
from typing import Any, SupportsFloat, SupportsInt, cast

import pandas as pd


def is_missing(value: object) -> bool:
    """None, pd.NA and float NaN (incl. numpy.float64) count as missing."""
    if value is None or value is pd.NA:
        return True
    return isinstance(value, float) and math.isnan(value)


def opt_float(value: object) -> float | None:
    return None if is_missing(value) else float(cast(SupportsFloat, value))


def opt_int(value: object) -> int | None:
    return None if is_missing(value) else int(cast(SupportsInt, value))


def opt_str(value: object) -> str | None:
    return None if is_missing(value) else str(value)


def rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame rows as dicts keyed by column name."""
    return [{str(k): v for k, v in row.items()} for row in df.to_dict(orient="records")]
