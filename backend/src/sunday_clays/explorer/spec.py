"""Explorer QuerySpec (C9): the validated JSON query the Explorer and every ChartCard send."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from sunday_clays.domain.round_type import RoundType


class Metric(StrEnum):
    SCORE = "score"
    ADJUSTED = "adjusted"
    RESIDUAL = "residual"
    RATING = "rating"
    ROUNDS = "rounds"
    SHOOTERS = "shooters"
    ATTENDANCE = "attendance"
    WINS = "wins"
    HIT_PCT = "hit_pct"
    DIFFICULTY = "difficulty"  # Plan 12: how the day played (event_metrics.difficulty)


class Agg(StrEnum):
    AVG = "avg"
    MEDIAN = "median"
    MAX = "max"
    MIN = "min"
    SUM = "sum"
    COUNT = "count"
    P90 = "p90"
    STDEV = "stdev"
    P25 = "p25"  # Plan 12: the low end (25th percentile)


class Dim(StrEnum):
    SHOOTER = "shooter"
    EVENT = "event"
    MONTH = "month"
    YEAR = "year"
    SEASON = "season"
    MONTH_OF_YEAR = "month_of_year"
    ROUND_TYPE = "round_type"
    GAUGE = "gauge"
    STATUS = "status"
    TEMP_BAND = "temp_band"
    WIND_BAND = "wind_band"
    PRECIP_BAND = "precip_band"
    CONDITION = "condition"
    STATION = "station"


class Filters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    shooter_ids: list[int] = []
    round_types: list[RoundType] = []
    statuses: list[str] = []
    gauges: list[str] = []
    temp_f: tuple[float, float] | None = None
    gust_mph: tuple[float, float] | None = None
    precip_in: tuple[float, float] | None = None
    min_rounds: int = 0
    best_round_only: bool = False
    min_score: int | None = Field(default=None, ge=0, le=50)  # Plan 12: rounds >= this score
    ytd: str | None = Field(default=None, pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


class QuerySpec(BaseModel):
    metric: Metric
    agg: Agg = Agg.AVG
    group_by: list[Dim] = Field(default=[], max_length=2)
    filters: Filters = Filters()
    sort: Literal["value_desc", "value_asc", "key_asc", "key_desc"] = "key_asc"
    limit: int = Field(default=500, le=5000)


class Column(BaseModel):
    key: str
    label: str
    type: Literal["date", "number", "string", "int"]


class QueryResult(BaseModel):
    columns: list[Column]
    rows: list[dict[str, str | int | float | None]]
    n_rounds: int
    truncated: bool
