"""Rebuild the live tables from the active imports and the active overlay rules (C4, C5)."""

from collections import Counter, defaultdict
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import bump_data_version
from sunday_clays.domain.diff import RowKey, StagedScore, keyed_rows, representative_names
from sunday_clays.domain.identity import (
    alias_rule_targets,
    identity_resolver,
    merge_map,
    resolve_shooter,
)
from sunday_clays.domain.imports import (
    SpecialSource,
    active_scores_import,
    active_special_sources,
    active_station_sources,
    load_staged_attendance,
    load_staged_scores,
)
from sunday_clays.domain.round_type import RoundType, classify_round_type
from sunday_clays.domain.rules import (
    ActiveRules,
    HideRoundPayload,
    ScoreOverridePayload,
    load_active_rules,
)
from sunday_clays.domain.station_link import LinkRound, StationEntry, link_station_entries
from sunday_clays.ingest.types import Finding, StationLayoutEntry
from sunday_clays.models import (
    AppState,
    Base,
    DataIssue,
    Event,
    ImportStationHit,
    ImportStationLayout,
    ImportStationSheet,
    Round,
    RoundMetric,
    Shooter,
    ShooterProfile,
    StationHit,
    StationLayout,
)

# The live models (C4) in DELETE order, children before parents: station_hits and round_metrics
# reference rounds, which references events. round_metrics is live only because of that FK; no
# other table has a foreign key into a live table.
_LIVE_MODELS: tuple[type[Base], ...] = (
    StationHit,
    RoundMetric,
    Round,
    ShooterProfile,
    StationLayout,
    DataIssue,
    Event,
)
LIVE_TABLES: tuple[str, ...] = tuple(str(model.__tablename__) for model in _LIVE_MODELS)
# pg_advisory_xact_lock key held by each rebuild until its transaction ends (migrations/env.py
# holds 7263001, domain.imports 7263002)
REBUILD_LOCK_KEY = 7263003
LEFT_CENSOR_DAYS = 56
REGULAR_TARGETS = 50  # a regular Sunday's round; a special Sunday carries its own total
# Inserts into tables with nullable columns pass execution_options(render_nulls=True): the ORM
# bulk insert otherwise drops None keys and sends one statement per run of equal key sets.


@dataclass
class RebuildReport:
    n_events: int
    n_rounds: int
    n_shooters: int
    n_station_events: int
    n_issues: int


@dataclass(frozen=True)
class _LiveRound:
    row: StagedScore
    ordinal: int
    score: int
    shooter_id: int


def rebuild_live(session: Session) -> RebuildReport:
    """Clear and rebuild every live table in the caller's transaction, then bump data_version.

    Rebuilds run one at a time: a second one waits for the first to commit, then rebuilds from
    what it committed. Readers never wait (see _clear_live_tables).
    """
    session.execute(select(func.pg_advisory_xact_lock(REBUILD_LOCK_KEY)))
    _clear_live_tables(session)
    issues: list[DataIssue] = []
    rules = load_active_rules(session)
    merges = merge_map(session)
    active_id = active_scores_import(session)
    specials = active_special_sources(session)
    staged, special_keys = _with_special_rows(
        session, load_staged_scores(session, active_id), specials, issues
    )
    rounds = _live_rounds(session, staged, rules, merges, issues, special_keys)
    # a special Sunday's own sheet wins over a station workbook tab of the same date
    sources = dict(
        sorted(
            {
                **active_station_sources(session),
                **{day: source.sheet_id for day, source in specials.items()},
            }.items()
        )
    )
    layouts = _station_layouts(session, sources)
    attendance = load_staged_attendance(session, active_id)
    n_events = _write_events(session, rounds, attendance, layouts, rules, issues, specials)
    _write_rounds(session, rounds)
    _write_station_data(session, sources, layouts, issues)
    n_profiles = _write_profiles(session, rounds, rules, merges, specials.keys())
    _note_merged_same_day(rounds, issues)
    session.add_all(issues)
    session.flush()
    bump_data_version(session)
    session.execute(
        pg_insert(AppState)
        .values(key="last_rebuild_at", value=func.to_jsonb(func.now()))
        .on_conflict_do_update(
            index_elements=[AppState.key], set_={"value": func.to_jsonb(func.now())}
        )
    )
    return RebuildReport(
        n_events=n_events,
        n_rounds=len(rounds),
        n_shooters=n_profiles,
        n_station_events=len(sources),
        n_issues=len(issues),
    )


def _clear_live_tables(session: Session) -> None:
    """Delete every live row and detach every ORM object the session loaded from the live tables.

    DELETE, not TRUNCATE: its ROW EXCLUSIVE lock never conflicts with a plain reader's ACCESS
    SHARE, so concurrent readers neither wait for the rebuild nor deadlock with it, and they keep
    seeing the old rows until the caller commits the new ones. Identity sequences are not
    restarted; no live id is stable across rebuilds.

    Without the expunge, the identity map would hand the caller its pre-rebuild object for a
    rebuilt natural key (events, shooter_profiles, station_layouts) or for a deleted id
    (``session.get``). Objects the caller still references become detached snapshots.
    """
    for name in LIVE_TABLES:  # Core deletes: no ORM synchronisation; the loop below detaches
        session.execute(delete(Base.metadata.tables[name]))
    for obj in list(session.identity_map.values()):
        if isinstance(obj, _LIVE_MODELS):
            session.expunge(obj)


def _rule_target_missing(
    rule_id: int, payload: ScoreOverridePayload | HideRoundPayload
) -> DataIssue:
    return DataIssue(
        code="rule_target_missing",
        severity="warning",
        event_date=payload.event_date,
        message=(
            f"Rule {rule_id} matches no round #{payload.ordinal} of {payload.name_key!r} "
            f"scored {payload.raw_score} on {payload.event_date.isoformat()}"
        ),
        details={"rule_id": rule_id, **payload.model_dump(mode="json")},
    )


def _with_special_rows(
    session: Session,
    weekly: list[StagedScore],
    specials: Mapping[date, SpecialSource],
    issues: list[DataIssue],
) -> tuple[list[StagedScore], set[str]]:
    """The scores import's rows minus any on a live special Sunday, plus every special row.

    A special import owns its date (Decision 13): weekly rows on it are left out and reported.
    Returns the rows and the name keys found on special sheets.
    """
    left_out = Counter(row.event_date for row in weekly if row.event_date in specials)
    for day, n in sorted(left_out.items()):
        issues.append(
            DataIssue(
                code="special_event_date_conflict",
                severity="warning",
                event_date=day,
                message=(
                    f"{n} scores-workbook rows on {day} are left out: {day} is the special"
                    f" shoot {specials[day].label!r}"
                ),
                details={"rows": n, "special_import_id": specials[day].import_id},
            )
        )
    special_rows = [
        row for source in specials.values() for row in load_staged_scores(session, source.import_id)
    ]
    kept = [row for row in weekly if row.event_date not in specials]
    return [*kept, *special_rows], {row.name_key for row in special_rows}


def _live_rounds(
    session: Session,
    staged: list[StagedScore],
    rules: ActiveRules,
    merges: dict[int, int],
    issues: list[DataIssue],
    special_keys: AbstractSet[str] = frozenset(),
) -> list[_LiveRound]:
    """Visible rounds with overridden scores; ordinals come from the raw rows, before any rule.

    A score_override or hide_round rule applies only to the row at its (event_date, name_key,
    ordinal) whose raw score is still the rule's raw_score; otherwise it is reported as
    rule_target_missing and never moved to another round (C5 rule targeting).
    """
    by_key = keyed_rows(staged)
    targeted: list[tuple[int, ScoreOverridePayload | HideRoundPayload]] = [
        *rules.hides,
        *rules.score_overrides,
    ]
    hidden: set[RowKey] = set()
    scores: dict[RowKey, int] = {}
    for rule_id, payload in sorted(targeted, key=lambda item: item[0]):
        key = (payload.event_date, payload.name_key, payload.ordinal)
        row = by_key.get(key)
        if row is None or row.score != payload.raw_score:
            issues.append(_rule_target_missing(rule_id, payload))
        elif isinstance(payload, HideRoundPayload):
            hidden.add(key)
        else:
            scores[key] = payload.score  # ascending ids: the newest override wins
    visible = [(key, row) for key, row in by_key.items() if key not in hidden]
    names = representative_names(staged)
    first_dates: dict[str, date] = {}
    for row in staged:
        first_dates.setdefault(row.name_key, row.event_date)
    # A name key on a special sheet with an alias_name rule goes to that rule's shooter
    # (Decision 15); every other key resolves exactly as before.
    ruled = alias_rule_targets(session) if special_keys else {}
    shooter_ids: dict[str, int] = {}
    for name_key in sorted({row.name_key for _, row in visible}):
        target = ruled.get(name_key) if name_key in special_keys else None
        shooter_id = (
            target
            if target is not None
            else resolve_shooter(session, names[name_key], first_dates[name_key])
        )
        shooter_ids[name_key] = merges.get(shooter_id, shooter_id)
    return [
        _LiveRound(row, key[2], scores.get(key, row.score), shooter_ids[row.name_key])
        for key, row in sorted(visible, key=lambda item: (item[1].event_date, item[1].row_number))
    ]


def _station_layouts(
    session: Session, sources: dict[date, int]
) -> dict[date, list[tuple[StationLayoutEntry, int]]]:
    """event_date -> [(layout entry, source import id)] for every active station sheet."""
    sheet_dates = {sheet_id: d for d, sheet_id in sources.items()}
    layouts: dict[date, list[tuple[StationLayoutEntry, int]]] = defaultdict(list)
    rows = session.execute(
        select(
            ImportStationLayout.sheet_id,
            ImportStationLayout.station_no,
            ImportStationLayout.station_label,
            ImportStationLayout.target_count,
            ImportStationSheet.import_id,
        )
        .join(ImportStationSheet, ImportStationSheet.id == ImportStationLayout.sheet_id)
        .where(ImportStationLayout.sheet_id.in_(list(sheet_dates)))
        .order_by(
            ImportStationLayout.sheet_id,
            ImportStationLayout.station_no,
            ImportStationLayout.station_label,
        )
    )
    for sheet_id, station_no, label, target_count, import_id in rows:
        layouts[sheet_dates[sheet_id]].append(
            (StationLayoutEntry(station_no, target_count, label), import_id)
        )
    return layouts


def _write_events(
    session: Session,
    rounds: list[_LiveRound],
    attendance: dict[date, int],
    layouts: dict[date, list[tuple[StationLayoutEntry, int]]],
    rules: ActiveRules,
    issues: list[DataIssue],
    specials: Mapping[date, SpecialSource] | None = None,
) -> int:
    specials = specials or {}
    n_rounds: dict[date, int] = defaultdict(int)
    shooters: dict[date, set[int]] = defaultdict(set)
    for rnd in rounds:
        n_rounds[rnd.row.event_date] += 1
        shooters[rnd.row.event_date].add(rnd.shooter_id)
    event_dates = set(n_rounds) | set(attendance) | set(layouts)
    rows: list[dict[str, Any]] = []
    for d in sorted(event_dates):
        head_count = attendance.get(d)
        n_shooters = len(shooters[d])
        has_scores = n_rounds[d] > 0
        complete = has_scores and (head_count is None or n_shooters >= 0.5 * head_count)
        special = specials.get(d)
        if d in rules.round_types:
            round_type, source = rules.round_types[d][1], "override"
        elif special is not None:
            round_type, source = RoundType.SPORTING, "none"  # Decision 16
        elif d in layouts:
            round_type, source = classify_round_type([e for e, _ in layouts[d]]), "stations"
        else:
            round_type, source = RoundType.SPORTING, "none"
        rows.append(
            {
                "event_date": d,
                "round_type": round_type.value,
                "round_type_source": source,
                "head_count": head_count,
                "n_rounds": n_rounds[d],
                "n_shooters": n_shooters,
                "has_scores": has_scores,
                "has_stations": d in layouts,
                "results_complete": complete,
                "kind": "regular" if special is None else "special",
                "label": None if special is None else special.label,
                "target_total": REGULAR_TARGETS if special is None else special.target_total,
            }
        )
        if has_scores and not complete:
            issues.append(
                DataIssue(
                    code="incomplete_results",
                    severity="warning",
                    event_date=d,
                    message=f"Only {n_shooters} of {head_count} shooters on {d} have scores",
                    details={"n_shooters": n_shooters, "head_count": head_count},
                )
            )
    for d, (rule_id, round_type) in sorted(rules.round_types.items()):
        if d not in event_dates:
            issues.append(
                DataIssue(
                    code="rule_target_missing",
                    severity="warning",
                    event_date=d,
                    message=f"Rule {rule_id} overrides the round type of {d}, which has no event",
                    details={
                        "rule_id": rule_id,
                        "event_date": d.isoformat(),
                        "round_type": round_type.value,
                    },
                )
            )
    if rows:
        session.execute(insert(Event).execution_options(render_nulls=True), rows)
    return len(rows)


def _write_rounds(session: Session, rounds: list[_LiveRound]) -> None:
    if not rounds:
        return
    session.execute(
        insert(Round).execution_options(render_nulls=True),
        [
            {
                "event_date": r.row.event_date,
                "shooter_id": r.shooter_id,
                "name_key": r.row.name_key,
                "ordinal": r.ordinal,
                "score": r.score,
                "gauge_class": r.row.gauge_class,
                "status": r.row.status,
                "source_row": r.row.row_number,
            }
            for r in rounds
        ],
    )


def _write_station_data(
    session: Session,
    sources: dict[date, int],
    layouts: dict[date, list[tuple[StationLayoutEntry, int]]],
    issues: list[DataIssue],
) -> None:
    if not sources:
        return
    session.execute(
        insert(StationLayout),
        [
            {
                "event_date": d,
                "station_no": entry.station_no,
                "station_label": entry.label,
                "target_count": entry.target_count,
                "source_import_id": import_id,
            }
            for d, entries in sorted(layouts.items())
            for entry, import_id in entries
        ],
    )
    sheet_dates = {sheet_id: d for d, sheet_id in sources.items()}
    hits = session.execute(
        select(
            ImportStationHit.sheet_id,
            ImportStationHit.row_number,
            ImportStationHit.raw_name,
            ImportStationHit.name_key,
            ImportStationHit.station_no,
            ImportStationHit.station_label,
            ImportStationHit.hits,
        )
        .where(ImportStationHit.sheet_id.in_(list(sheet_dates)))
        .order_by(
            ImportStationHit.sheet_id,
            ImportStationHit.row_number,
            ImportStationHit.station_no,
            ImportStationHit.station_label,
        )
    ).all()
    totals: dict[tuple[date, int], int] = defaultdict(int)
    names: dict[tuple[date, int], tuple[str, str]] = {}
    for sheet_id, row_number, raw_name, key, _, _, value in hits:
        entry_key = (sheet_dates[sheet_id], row_number)
        totals[entry_key] += value
        names.setdefault(entry_key, (raw_name, key))
    resolve = identity_resolver(session)  # after _live_rounds created this rebuild's aliases
    entries = [
        StationEntry(d, row, raw, key, resolve(key), totals[(d, row)])
        for (d, row), (raw, key) in sorted(names.items())
    ]
    # columns, not Round entities: the identity map can never hand this link a stale row
    link_rounds = [
        LinkRound(round_id, event_date, shooter_id, ordinal, score)
        for round_id, event_date, shooter_id, ordinal, score in session.execute(
            select(Round.id, Round.event_date, Round.shooter_id, Round.ordinal, Round.score).where(
                Round.event_date.in_(list(sources))
            )
        )
    ]
    links, findings = link_station_entries(entries, link_rounds)
    link_by_entry = {(link.event_date, link.entry_row): link for link in links}
    session.execute(
        insert(StationHit).execution_options(render_nulls=True),
        [
            {
                "event_date": sheet_dates[sheet_id],
                "station_no": station_no,
                "station_label": label,
                "sheet_id": sheet_id,
                "entry_row": row_number,
                "name_key": key,
                "shooter_id": link_by_entry[(sheet_dates[sheet_id], row_number)].shooter_id,
                "round_id": link_by_entry[(sheet_dates[sheet_id], row_number)].round_id,
                "hits": value,
            }
            for sheet_id, row_number, _, key, station_no, label, value in hits
        ],
    )
    entry_by_key: dict[tuple[date | None, int | None], StationEntry] = {
        (e.event_date, e.entry_row): e for e in entries
    }
    score_by_round = {r.round_id: r.score for r in link_rounds}
    for finding in findings:
        entry = entry_by_key[(finding.event_date, finding.row)]
        link = link_by_entry[(entry.event_date, entry.entry_row)]
        details: dict[str, Any] = {
            "name_key": entry.name_key,
            "raw_name": entry.raw_name,
            "event_date": entry.event_date.isoformat(),
            "entry_row": entry.entry_row,
            "station_total": entry.total,
        }
        if link.round_id is not None:
            details["round_id"] = link.round_id
            details["score"] = score_by_round[link.round_id]
        issues.append(_station_issue(finding, entry.shooter_id, details))


def _station_issue(finding: Finding, shooter_id: int | None, details: dict[str, Any]) -> DataIssue:
    return DataIssue(
        code=finding.code,
        severity=finding.severity.value,
        event_date=finding.event_date,
        shooter_id=shooter_id,
        message=finding.message,
        details=details,
    )


def _write_profiles(
    session: Session,
    rounds: list[_LiveRound],
    rules: ActiveRules,
    merges: dict[int, int],
    special_dates: AbstractSet[date] = frozenset(),
) -> int:
    if not rounds:
        return 0
    renames = _by_merge_target(rules.renames, merges)
    statuses = _by_merge_target(rules.statuses, merges)
    earliest = min(r.row.event_date for r in rounds)
    by_shooter: dict[int, list[_LiveRound]] = defaultdict(list)
    for rnd in rounds:
        by_shooter[rnd.shooter_id].append(rnd)
    display: dict[int, str] = dict(
        session.execute(
            select(Shooter.id, Shooter.display_name).where(Shooter.id.in_(list(by_shooter)))
        ).all()
    )
    rows: list[dict[str, Any]] = []
    for shooter_id, own in sorted(by_shooter.items()):
        dates = {r.row.event_date for r in own}
        first_event = min(dates)
        rows.append(
            {
                "shooter_id": shooter_id,
                "display_name": renames.get(shooter_id, display[shooter_id]),
                "status": statuses.get(shooter_id, _profile_status(own)),
                "first_event": first_event,
                "last_event": max(dates),
                # Sundays shot count every appearance; rounds count scored (regular) rounds only
                "n_rounds": sum(1 for r in own if r.row.event_date not in special_dates),
                "n_events": len(dates),
                "left_censored": first_event < earliest + timedelta(days=LEFT_CENSOR_DAYS),
            }
        )
    session.execute(insert(ShooterProfile), rows)
    return len(rows)


def _by_merge_target(rules: dict[int, tuple[int, str]], merges: dict[int, int]) -> dict[int, str]:
    """Rename/status values keyed by the shooter each rule's shooter now merges into.

    Folding in ascending rule id lets the newest rule win when several land on one shooter.
    """
    values: dict[int, str] = {}
    for shooter_id, (_, value) in sorted(rules.items(), key=lambda item: item[1][0]):
        values[merges.get(shooter_id, shooter_id)] = value
    return values


def _profile_status(rounds: list[_LiveRound]) -> str:
    """'deceased' if any round says so, else the most recent recorded status, else 'guest'."""
    if any(r.row.status == "deceased" for r in rounds):
        return "deceased"
    recorded = [r for r in rounds if r.row.status is not None]
    if not recorded:
        return "guest"
    latest = min(recorded, key=lambda r: (-r.row.event_date.toordinal(), r.ordinal, r.row.name_key))
    return str(latest.row.status)


def _note_merged_same_day(rounds: list[_LiveRound], issues: list[DataIssue]) -> None:
    """INFO issue per (date, shooter) whose rounds carry two or more name_keys (merges, C5)."""
    keys: dict[tuple[date, int], set[str]] = defaultdict(set)
    for rnd in rounds:
        keys[(rnd.row.event_date, rnd.shooter_id)].add(rnd.row.name_key)
    for (d, shooter_id), name_keys in sorted(keys.items()):
        if len(name_keys) >= 2:
            issues.append(
                DataIssue(
                    code="merged_same_day_rounds",
                    severity="info",
                    event_date=d,
                    shooter_id=shooter_id,
                    message=f"Shooter {shooter_id} has rounds under {len(name_keys)} names on {d}",
                    details={"name_keys": sorted(name_keys)},
                )
            )
