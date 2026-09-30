"""Import staging, previews and the active imports (C5)."""

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session, defer

from sunday_clays.domain.diff import (
    SheetContent,
    StagedScore,
    assign_ordinals,
    attendance_by_date,
    attendance_changes,
    possible_duplicate_pairs,
    representative_names,
    score_row_changes,
    station_changes,
)
from sunday_clays.domain.errors import ConflictError, NotFoundError
from sunday_clays.domain.identity import identity_resolver, merge_map
from sunday_clays.domain.schemas import (
    FindingOut,
    ImportPreview,
    ImportSummary,
    ScoresDiff,
    StationsDiff,
    finding_out,
)
from sunday_clays.domain.station_link import LinkRound, StationEntry, link_station_entries
from sunday_clays.ingest import parse_upload
from sunday_clays.ingest.names import clean_display_name, identity_key, name_key
from sunday_clays.ingest.types import (
    STATION_SHEET_EXCLUSION_CODES,
    FileKind,
    Finding,
    ScoresParse,
    StationsParse,
)
from sunday_clays.models import (
    Import,
    ImportAttendanceRow,
    ImportScoreRow,
    ImportStationHit,
    ImportStationLayout,
    ImportStationSheet,
    Round,
    Shooter,
    ShooterAlias,
    StationHit,
)

PREVIEW_STATION_CODES = frozenset(
    {"station_score_mismatch", "station_name_unmatched", "station_round_ambiguous"}
)

# (event_date, entry_row) -> station tab name, used to label preview station findings
TabIndex = Mapping[tuple[date | None, int | None], str]

# pg_advisory_xact_lock key taken by commit/discard/rollback (migrations/env.py holds 7263001)
IMPORT_LIFECYCLE_LOCK_KEY = 7263002


# --- active sources ------------------------------------------------------------------------
def active_scores_import(session: Session) -> int | None:
    """Id of the most recently committed scores import, or None."""
    return session.scalar(
        select(Import.id)
        .where(Import.kind == FileKind.SCORES.value, Import.status == "committed")
        .order_by(Import.committed_at.desc(), Import.id.desc())
        .limit(1)
    )


def active_station_sources(session: Session) -> dict[date, int]:
    """event_date -> station sheet id from the newest committed stations import with that date."""
    rows = session.execute(
        select(ImportStationSheet.event_date, ImportStationSheet.id)
        .join(Import, Import.id == ImportStationSheet.import_id)
        .where(Import.kind == FileKind.STATIONS.value, Import.status == "committed")
        .order_by(Import.committed_at.desc(), Import.id.desc(), ImportStationSheet.id)
    ).all()
    sources: dict[date, int] = {}
    for event_date, sheet_id in rows:
        sources.setdefault(event_date, sheet_id)
    return dict(sorted(sources.items()))


# --- staged row loaders ----------------------------------------------------------------------
def load_staged_scores(session: Session, import_id: int | None) -> list[StagedScore]:
    if import_id is None:
        return []
    rows = session.scalars(
        select(ImportScoreRow)
        .where(ImportScoreRow.import_id == import_id)
        .order_by(ImportScoreRow.row_number)
    )
    return [
        StagedScore(
            row_id=r.id,
            row_number=r.row_number,
            raw_name=r.raw_name,
            name_key=r.name_key,
            event_date=r.event_date,
            score=r.score,
            status=r.status,
            gauge_class=r.gauge_class,
        )
        for r in rows
    ]


def load_staged_attendance(session: Session, import_id: int | None) -> dict[date, int]:
    if import_id is None:
        return {}
    rows = session.execute(
        select(
            ImportAttendanceRow.row_number,
            ImportAttendanceRow.event_date,
            ImportAttendanceRow.head_count,
        ).where(ImportAttendanceRow.import_id == import_id)
    ).all()
    return attendance_by_date((r[0], r[1], r[2]) for r in rows)


def sheet_contents(session: Session, sheet_ids: dict[date, int]) -> dict[date, SheetContent]:
    """Comparable content (layout + hits by name_key) of each station sheet."""
    ids = list(sheet_ids.values())
    layouts: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for sheet_id, label, target in session.execute(
        select(
            ImportStationLayout.sheet_id,
            ImportStationLayout.station_label,
            ImportStationLayout.target_count,
        ).where(ImportStationLayout.sheet_id.in_(ids))
    ):
        layouts[sheet_id].append((label, target))
    hits: dict[int, list[tuple[str, str, int]]] = defaultdict(list)
    for sheet_id, key, label, value in session.execute(
        select(
            ImportStationHit.sheet_id,
            ImportStationHit.name_key,
            ImportStationHit.station_label,
            ImportStationHit.hits,
        ).where(ImportStationHit.sheet_id.in_(ids))
    ):
        hits[sheet_id].append((key, label, value))
    return {
        d: (tuple(sorted(layouts[sid])), tuple(sorted(hits[sid]))) for d, sid in sheet_ids.items()
    }


# --- staging -------------------------------------------------------------------------------
def _stage_scores(session: Session, import_id: int, parsed: ScoresParse) -> None:
    if parsed.score_rows:
        session.execute(
            insert(ImportScoreRow),
            [
                {
                    "import_id": import_id,
                    "row_number": r.row_number,
                    "raw_name": r.raw_name,
                    "name_key": identity_key(name_key(r.raw_name), r.event_date),
                    "score": r.score,
                    "event_date": r.event_date,
                    "status": r.status,
                    "gauge_class": r.gauge_class,
                }
                for r in parsed.score_rows
            ],
        )
    if parsed.attendance_rows:
        session.execute(
            insert(ImportAttendanceRow),
            [
                {
                    "import_id": import_id,
                    "row_number": a.row_number,
                    "event_date": a.event_date,
                    "head_count": a.head_count,
                }
                for a in parsed.attendance_rows
            ],
        )


def _stage_stations(session: Session, import_id: int, parsed: StationsParse) -> dict[date, int]:
    staged: dict[date, int] = {}
    for sheet in parsed.sheets:
        row = ImportStationSheet(
            import_id=import_id, sheet_name=sheet.sheet_name, event_date=sheet.event_date
        )
        session.add(row)
        session.flush()
        staged[sheet.event_date] = row.id
        session.execute(
            insert(ImportStationLayout),
            [
                {
                    "sheet_id": row.id,
                    "station_no": e.station_no,
                    "station_label": e.label,
                    "target_count": e.target_count,
                }
                for e in sheet.layout
            ],
        )
        number_of = {e.label: e.station_no for e in sheet.layout}
        hit_rows = [
            {
                "sheet_id": row.id,
                "row_number": r.row_number,
                "raw_name": r.raw_name,
                "name_key": identity_key(name_key(r.raw_name), sheet.event_date),
                "station_no": number_of[label],
                "station_label": label,
                "hits": hits,
            }
            for r in sheet.rows
            for label, hits in r.hits
        ]
        session.execute(insert(ImportStationHit), hit_rows)  # kept sheets always have rows
    return staged


# --- preview -------------------------------------------------------------------------------
def _station_findings(
    entries: list[StationEntry], rounds: list[LinkRound], tabs: TabIndex
) -> list[Finding]:
    """The C5 preview codes in entry order, labelled with the station tab and a cleaned name.

    Both callers pass entries in (event_date, entry_row) order; the sort is stable, so one entry's
    findings keep link_station_entries' order.
    """
    _, findings = link_station_entries(entries, rounds)
    position: dict[tuple[date | None, int | None], int] = {
        (e.event_date, e.entry_row): i for i, e in enumerate(entries)
    }
    kept = sorted(
        (f for f in findings if f.code in PREVIEW_STATION_CODES),
        key=lambda f: position[(f.event_date, f.row)],
    )
    return [
        replace(f, sheet=tabs[(f.event_date, f.row)], name=clean_display_name(f.name or ""))
        for f in kept
    ]


def _preview_scores(session: Session, import_id: int) -> tuple[ScoresDiff, list[Finding]]:
    new_rows = load_staged_scores(session, import_id)
    active_id = active_scores_import(session)
    old_rows = load_staged_scores(session, active_id)
    changes = score_row_changes(new_rows, old_rows)
    attendance = attendance_changes(
        load_staged_attendance(session, import_id), load_staged_attendance(session, active_id)
    )
    aliases: dict[str, int] = dict(
        session.execute(select(ShooterAlias.name_key, ShooterAlias.shooter_id)).all()
    )
    staged_names = representative_names(new_rows)
    new_keys = sorted(staged_names.keys() - aliases.keys())
    key_dates: dict[str, set[date]] = defaultdict(set)
    for key, event_date in session.execute(select(Round.name_key, Round.event_date).distinct()):
        key_dates[key].add(event_date)
    for key in aliases:
        key_dates.setdefault(key, set())
    staged_dates: dict[str, set[date]] = defaultdict(set)
    for row in new_rows:
        staged_dates[row.name_key].add(row.event_date)
    key_dates.update(staged_dates)
    display: dict[str, str] = dict(
        session.execute(
            select(ShooterAlias.name_key, Shooter.display_name).join(
                Shooter, Shooter.id == ShooterAlias.shooter_id
            )
        ).all()
    )
    display.update({k: clean_display_name(raw) for k, raw in staged_names.items()})
    diff = ScoresDiff(
        events_added=changes.events_added,
        events_removed=changes.events_removed,
        rows_added=changes.rows_added,
        rows_removed=changes.rows_removed,
        rows_changed=changes.rows_changed,
        new_names=sorted(display[k] for k in new_keys),
        possible_duplicates=possible_duplicate_pairs(new_keys, key_dates, display),
        attendance_changed=attendance,
    )
    return diff, _scores_station_findings(session, new_rows, aliases)


def _scores_station_findings(
    session: Session, new_rows: Sequence[StagedScore], aliases: dict[str, int]
) -> list[Finding]:
    live = session.execute(
        select(
            StationHit.event_date,
            StationHit.entry_row,
            StationHit.name_key,
            func.sum(StationHit.hits),
            func.min(ImportStationHit.raw_name),
            func.min(ImportStationSheet.sheet_name),
        )
        .join(
            ImportStationHit,
            (ImportStationHit.sheet_id == StationHit.sheet_id)
            & (ImportStationHit.row_number == StationHit.entry_row)
            & (ImportStationHit.station_label == StationHit.station_label),
        )
        .join(ImportStationSheet, ImportStationSheet.id == StationHit.sheet_id)
        .group_by(StationHit.event_date, StationHit.entry_row, StationHit.name_key)
        .order_by(StationHit.event_date, StationHit.entry_row)
    ).all()
    if not live:
        return []
    station_dates = {row[0] for row in live}
    merges = merge_map(session)
    new_ids: dict[str, int] = {}

    def shooter_for(key: str) -> int:
        if key in aliases:
            return merges.get(aliases[key], aliases[key])
        return new_ids.setdefault(key, -(len(new_ids) + 1))

    # Every staged name gets its id, including names with no row on a station date (Decision 11).
    shooter_of = {r.name_key: shooter_for(r.name_key) for r in new_rows}
    dated = [r for r in new_rows if r.event_date in station_dates]
    ordinals = assign_ordinals(dated)
    rounds = [
        LinkRound(r.row_id, r.event_date, shooter_of[r.name_key], ordinals[r.row_id], r.score)
        for r in dated
    ]
    resolve = identity_resolver(session)
    entries: list[StationEntry] = []
    tabs: dict[tuple[date | None, int | None], str] = {}
    for event_date, entry_row, key, total, raw_name, tab in live:
        shooter_id = resolve(key)
        if shooter_id is None:
            shooter_id = new_ids.get(key)
        entries.append(StationEntry(event_date, entry_row, raw_name, key, shooter_id, int(total)))
        tabs[(event_date, entry_row)] = tab
    return _station_findings(entries, rounds, tabs)


def _preview_stations(
    session: Session, staged: dict[date, int], parsed: StationsParse
) -> tuple[StationsDiff, list[Finding]]:
    added, replaced, unchanged = station_changes(
        sheet_contents(session, staged), sheet_contents(session, active_station_sources(session))
    )
    skipped = sorted(
        {
            f.sheet
            for f in parsed.findings
            if f.code in STATION_SHEET_EXCLUSION_CODES and f.sheet is not None
        }
    )
    diff = StationsDiff(
        events_added=added,
        events_replaced=replaced,
        events_unchanged=unchanged,
        sheets_skipped=skipped,
    )
    resolve = identity_resolver(session)
    entries: list[StationEntry] = []
    tabs: dict[tuple[date | None, int | None], str] = {}
    for sheet in parsed.sheets:
        for row in sheet.rows:
            key = identity_key(name_key(row.raw_name), sheet.event_date)
            entries.append(
                StationEntry(
                    sheet.event_date,
                    row.row_number,
                    row.raw_name,
                    key,
                    resolve(key),
                    sum(hits for _, hits in row.hits),
                )
            )
            tabs[(sheet.event_date, row.row_number)] = sheet.sheet_name
    rounds = [
        LinkRound(r.id, r.event_date, r.shooter_id, r.ordinal, r.score)
        for r in session.scalars(select(Round).where(Round.event_date.in_(list(staged))))
    ]
    return diff, _station_findings(entries, rounds, tabs)


def _placed_findings(parsed: ScoresParse | StationsParse) -> list[Finding]:
    """Scores-level non_sunday_date findings have no sheet or row: say where the date occurs."""
    if not isinstance(parsed, ScoresParse):
        return list(parsed.findings)
    places = {
        "score rows": {r.event_date for r in parsed.score_rows},
        "Attendance History": {a.event_date for a in parsed.attendance_rows},
    }
    return [
        replace(f, message=f"{f.message} (in {_where(f.event_date, places)})")
        if f.code == "non_sunday_date" and f.sheet is None
        else f
        for f in parsed.findings
    ]


def _where(day: date | None, places: Mapping[str, set[date]]) -> str:
    return " and ".join(place for place, dates in places.items() if day in dates)


def stage_import(session: Session, data: bytes, filename: str) -> ImportPreview:
    """Parse, stage and preview an upload; an already pending/committed file returns its preview."""
    sha256 = hashlib.sha256(data).hexdigest()
    # Held until the caller's transaction ends: a concurrent upload of the same bytes waits here,
    # then its duplicate query sees this import (Decision 7).
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(sha256, 0))))
    duplicate = session.scalar(
        select(Import.id)
        .where(Import.sha256 == sha256, Import.status.in_(("pending", "committed")))
        .order_by(Import.id.desc())
        .limit(1)
    )
    if duplicate is not None:
        return get_import_preview(session, duplicate).model_copy(update={"duplicate_of": duplicate})
    parsed = parse_upload(data)
    imp = Import(kind=parsed.kind.value, filename=filename, sha256=sha256, file_bytes=data)
    session.add(imp)
    session.flush()
    diff: ScoresDiff | StationsDiff
    if isinstance(parsed, ScoresParse):
        _stage_scores(session, imp.id, parsed)
        diff, station_findings = _preview_scores(session, imp.id)
        requires_confirmation = bool(diff.events_removed) or diff.rows_removed > 0
    else:
        staged = _stage_stations(session, imp.id, parsed)
        diff, station_findings = _preview_stations(session, staged, parsed)
        requires_confirmation = False
    findings = [finding_out(f) for f in (*_placed_findings(parsed), *station_findings)]
    imp.findings = [f.model_dump(mode="json") for f in findings]
    imp.summary = {
        "diff": diff.model_dump(mode="json"),
        "requires_removal_confirmation": requires_confirmation,
    }
    session.flush()
    return ImportPreview(
        import_id=imp.id,
        kind=parsed.kind,
        filename=filename,
        duplicate_of=None,
        findings=findings,
        diff=diff,
        requires_removal_confirmation=requires_confirmation,
    )


def get_import_preview(session: Session, import_id: int) -> ImportPreview:
    """The preview stored when the import was staged."""
    imp = _get_import(session, import_id)
    kind = FileKind(imp.kind)
    stored = imp.summary["diff"]
    diff = (
        ScoresDiff.model_validate(stored)
        if kind is FileKind.SCORES
        else StationsDiff.model_validate(stored)
    )
    return ImportPreview(
        import_id=imp.id,
        kind=kind,
        filename=imp.filename,
        duplicate_of=None,
        findings=[FindingOut.model_validate(f) for f in imp.findings],
        diff=diff,
        requires_removal_confirmation=imp.summary["requires_removal_confirmation"],
    )


def _get_import(session: Session, import_id: int) -> Import:
    imp = session.get(Import, import_id, options=[defer(Import.file_bytes)])
    if imp is None:
        raise NotFoundError("import_not_found", f"Import {import_id} does not exist")
    return imp


# --- lifecycle -----------------------------------------------------------------------------
def _lock_for_lifecycle(session: Session, import_id: int) -> Import:
    """Serialize every status change, then read the target import's current row FOR UPDATE.

    The advisory lock is held until the caller's transaction ends. A concurrent commit, discard
    or rollback waits here, then its statements see the winner's committed state, so the removal
    re-diff runs against the import that is really live (Decision 8).
    """
    session.execute(select(func.pg_advisory_xact_lock(IMPORT_LIFECYCLE_LOCK_KEY)))
    imp = session.get(
        Import,
        import_id,
        options=[defer(Import.file_bytes)],
        with_for_update=True,
        populate_existing=True,  # a copy loaded before the wait may be stale
    )
    if imp is None:
        raise NotFoundError("import_not_found", f"Import {import_id} does not exist")
    return imp


def commit_import(session: Session, import_id: int, *, confirm_removals: bool = False) -> None:
    """pending -> committed. Removal check is re-run against the scores import live right now."""
    imp = _lock_for_lifecycle(session, import_id)
    if imp.status != "pending":
        raise ConflictError("not_pending", f"Import {import_id} is {imp.status}, not pending")
    if imp.kind == FileKind.SCORES.value and not confirm_removals:
        changes = score_row_changes(
            load_staged_scores(session, import_id),
            load_staged_scores(session, active_scores_import(session)),
        )
        if changes.events_removed or changes.rows_removed:
            raise ConflictError(
                "removals_not_confirmed",
                f"This file removes {len(changes.events_removed)} events and "
                f"{changes.rows_removed} rows; commit again with confirm_removals=true",
            )
    imp.status = "committed"
    imp.committed_at = func.clock_timestamp()
    session.flush()


def discard_import(session: Session, import_id: int) -> None:
    imp = _lock_for_lifecycle(session, import_id)
    if imp.status != "pending":
        raise ConflictError("not_pending", f"Import {import_id} is {imp.status}, not pending")
    imp.status = "discarded"
    session.flush()


def rollback_import(session: Session, import_id: int) -> None:
    imp = _lock_for_lifecycle(session, import_id)
    if imp.status != "committed":
        raise ConflictError("not_committed", f"Import {import_id} is {imp.status}, not committed")
    imp.status = "rolled_back"
    imp.rolled_back_at = func.clock_timestamp()
    session.flush()


def list_imports(session: Session) -> list[ImportSummary]:
    """Every import, newest first, without file bytes."""
    rows = session.scalars(
        select(Import).options(defer(Import.file_bytes)).order_by(Import.id.desc())
    )
    return [ImportSummary.model_validate(imp) for imp in rows]
