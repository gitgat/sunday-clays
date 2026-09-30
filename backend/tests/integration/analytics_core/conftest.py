"""Plan 06 integration helpers: seed live tables directly (no imports, no rebuild)."""

from dataclasses import asdict
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import bump_data_version
from sunday_clays.analytics.skill import SkillParams
from sunday_clays.analytics.steps import s10_metrics, s30_skill


class LiveSeed:
    """Writes events/rounds/shooter_profiles/event_weather rows like rebuild_live."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._profiles: dict[int, tuple[str, str, bool]] = {}
        self._keys: dict[int, str] = {}
        self._events: set[date] = set()
        self._row = 0

    def shooter(self, name: str, *, status: str = "member", left_censored: bool = False) -> int:
        sid = int(
            self.session.execute(
                text(
                    "INSERT INTO shooters (display_name, created_at)"
                    " VALUES (:n, now()) RETURNING id"
                ),
                {"n": name},
            ).scalar_one()
        )
        self._profiles[sid] = (name, status, left_censored)
        self._keys[sid] = name.casefold().replace(",", "")
        return sid

    def event(
        self,
        d: date,
        *,
        held: bool = True,
        head_count: int | None = None,
        round_type: str | None = None,
        has_scores: bool = True,
        has_stations: bool = False,
    ) -> None:
        source = "none" if round_type is None else "override"
        self.session.execute(
            text(
                "INSERT INTO events (event_date, round_type, round_type_source,"
                " head_count, n_rounds, n_shooters, has_scores, has_stations,"
                " results_complete)"
                " VALUES (:d, :rt, :src, :hc, 0, 0, :hs, :hst, :rc)"
            ),
            {
                "d": d,
                "rt": round_type or "sporting",
                "src": source,
                "hc": head_count,
                "hs": has_scores,
                "hst": has_stations,
                "rc": held,
            },
        )
        self._events.add(d)

    def round(
        self,
        d: date,
        shooter_id: int,
        score: int,
        *,
        name_key: str | None = None,
        ordinal: int | None = None,
        gauge_class: str | None = None,
        status: str | None = "member",
    ) -> int:
        if d not in self._events:
            self.event(d)
        key = name_key if name_key is not None else self._keys[shooter_id]
        if ordinal is None:
            ordinal = 1 + int(
                self.session.execute(
                    text("SELECT count(*) FROM rounds WHERE event_date = :d AND name_key = :k"),
                    {"d": d, "k": key},
                ).scalar_one()
            )
        self._row += 1
        return int(
            self.session.execute(
                text(
                    "INSERT INTO rounds (event_date, shooter_id, name_key, ordinal,"
                    " score, gauge_class, status, source_row)"
                    " VALUES (:d, :s, :k, :o, :sc, :g, :st, :row) RETURNING id"
                ),
                {
                    "d": d,
                    "s": shooter_id,
                    "k": key,
                    "o": ordinal,
                    "sc": score,
                    "g": gauge_class,
                    "st": status,
                    "row": self._row,
                },
            ).scalar_one()
        )

    def weather(
        self,
        d: date,
        *,
        temp_f: float = 55.0,
        gust_mph: float = 5.0,
        precip_in: float = 0.0,
        cloud_pct: float = 20.0,
        condition: str = "clear",
    ) -> None:
        self.session.execute(
            text(
                "INSERT INTO event_weather (event_date, temp_f, apparent_f, precip_in,"
                " wind_mph, gust_mph, wind_dir_deg, cloud_pct, humidity_pct,"
                " pressure_hpa, condition, source)"
                " VALUES (:d, :t, :t, :p, :w, :g, 180, :c, 60, 1015, :cond, 'archive')"
            ),
            {
                "d": d,
                "t": temp_f,
                "p": precip_in,
                "w": gust_mph / 2,
                "g": gust_mph,
                "c": cloud_pct,
                "cond": condition,
            },
        )

    def finish(self) -> None:
        """Fill events.n_rounds/n_shooters and shooter_profiles; bump data_version."""
        self.session.execute(
            text(
                "UPDATE events e SET n_rounds = c.n, n_shooters = c.s"
                " FROM (SELECT event_date, count(*) AS n,"
                " count(DISTINCT shooter_id) AS s FROM rounds GROUP BY event_date) c"
                " WHERE e.event_date = c.event_date"
            )
        )
        self.session.execute(text("DELETE FROM shooter_profiles"))
        for sid, (name, status, left_censored) in self._profiles.items():
            self.session.execute(
                text(
                    "INSERT INTO shooter_profiles (shooter_id, display_name, status,"
                    " first_event, last_event, n_rounds, n_events, left_censored)"
                    " SELECT :s, :n, :st, min(event_date), max(event_date), count(*),"
                    " count(DISTINCT event_date), :lc FROM rounds WHERE shooter_id = :s"
                    " HAVING count(*) > 0"
                ),
                {"s": sid, "n": name, "st": status, "lc": left_censored},
            )
        self.bump()

    def analyze(self, params: SkillParams | None = None) -> None:
        """Store `params` (default SkillParams()) as skill_params; run s10 + s30."""
        s30_skill.store_state(self.session, "skill_params", asdict(params or SkillParams()))
        s10_metrics.STEP.run(self.session)
        s30_skill.STEP.run(self.session)
        self.bump()

    def bump(self) -> None:
        """Advance `app_state.data_version` the way rebuild/run_pipeline do (Plan 03 T7)."""
        bump_data_version(self.session)


@pytest.fixture
def seed(session: Session) -> LiveSeed:
    return LiveSeed(session)
