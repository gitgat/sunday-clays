"""ORM models for every C4 table; importing this package registers them all on ``Base.metadata``."""

from sunday_clays.models.analytics import (
    AchievementAwarded,
    EventMetric,
    RatingHistory,
    RoundMetric,
)
from sunday_clays.models.base import Base
from sunday_clays.models.identity import AuditLog, LoginAttempt, Rule, Shooter, ShooterAlias
from sunday_clays.models.insights import Insight, InsightPick
from sunday_clays.models.live import (
    DataIssue,
    Event,
    Round,
    ShooterProfile,
    StationHit,
    StationLayout,
)
from sunday_clays.models.ops import AppState, Job
from sunday_clays.models.staging import (
    Import,
    ImportAttendanceRow,
    ImportScoreRow,
    ImportStationHit,
    ImportStationLayout,
    ImportStationSheet,
)
from sunday_clays.models.weather import EventWeather, ForecastCache, WeatherHourly

__all__ = [
    "AchievementAwarded",
    "AppState",
    "AuditLog",
    "Base",
    "DataIssue",
    "Event",
    "EventMetric",
    "EventWeather",
    "ForecastCache",
    "Import",
    "ImportAttendanceRow",
    "ImportScoreRow",
    "ImportStationHit",
    "ImportStationLayout",
    "ImportStationSheet",
    "Insight",
    "InsightPick",
    "Job",
    "LoginAttempt",
    "RatingHistory",
    "Round",
    "RoundMetric",
    "Rule",
    "Shooter",
    "ShooterAlias",
    "ShooterProfile",
    "StationHit",
    "StationLayout",
    "WeatherHourly",
]
