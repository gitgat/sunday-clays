import { useId } from 'react';
import { Card } from '../../../components/ui/Card';
import type { ImportPreview, ScoresDiff, StationsDiff } from '../api';
import { dateList, formatDay } from '../format';

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

/** A few dates inline; a first or full import adds hundreds, so those get a count and an expandable list. */
const INLINE_DATES = 5;

function EventsAdded({ dates }: { dates: string[] }) {
  if (dates.length <= INLINE_DATES) return <Row label="Events added" value={dateList(dates)} />;
  return (
    <div className="col-span-full flex flex-col">
      <dt className="text-xs text-text-muted">Events added</dt>
      <dd>
        <details>
          <summary className="min-h-11 cursor-pointer py-2.5">{`${dates.length} events`}</summary>
          <p>{dateList(dates)}</p>
        </details>
      </dd>
    </div>
  );
}

function Removals({ diff }: { diff: ScoresDiff }) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className="flex flex-col gap-2 rounded-card border-2 border-error-container p-3"
    >
      <h3 id={id} className="font-medium text-error">
        Removals
      </h3>
      <p>
        {`This file is missing ${diff.events_removed.length} events and ${diff.rows_removed} rows that are live now. Committing it removes them.`}
      </p>
      {diff.events_removed.length > 0 && (
        <ul aria-label="Removed events" className="flex flex-wrap gap-2">
          {diff.events_removed.map((d) => (
            <li key={d} className="rounded-button border border-error-container px-2">
              {formatDay(d)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ScoresDiffView({ diff }: { diff: ScoresDiff }) {
  return (
    <div className="flex flex-col gap-3">
      {(diff.events_removed.length > 0 || diff.rows_removed > 0) && <Removals diff={diff} />}
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <EventsAdded dates={diff.events_added} />
        <Row label="Rows added" value={String(diff.rows_added)} />
        <Row label="Rows changed" value={String(diff.rows_changed)} />
        <Row label="Rows removed" value={String(diff.rows_removed)} />
        <Row label="Head counts changed" value={String(diff.attendance_changed)} />
      </dl>
      {diff.new_names.length > 0 && (
        <details>
          <summary className="min-h-11 cursor-pointer py-2.5">{`New names (${diff.new_names.length})`}</summary>
          <ul className="flex flex-col">
            {diff.new_names.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      )}
      {diff.possible_duplicates.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="font-medium">Possible duplicates</h3>
          <ul className="flex flex-col">
            {diff.possible_duplicates.map(([a, b]) => (
              <li key={`${a}|${b}`}>{`${a} ↔ ${b}`}</li>
            ))}
          </ul>
          <p className="text-xs text-text-muted">
            New names are new shooters; merge real duplicates later under Identity.
          </p>
        </div>
      )}
    </div>
  );
}

function StationsDiffView({ diff }: { diff: StationsDiff }) {
  return (
    <div className="flex flex-col gap-3">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Row label="Weeks added" value={dateList(diff.events_added)} />
        <Row label="Weeks replaced" value={dateList(diff.events_replaced)} />
        <Row label="Weeks unchanged" value={dateList(diff.events_unchanged)} />
      </dl>
      {diff.sheets_skipped.length > 0 && (
        <p className="text-sm text-text-muted">{`Skipped tabs: ${diff.sheets_skipped.join(', ')}`}</p>
      )}
    </div>
  );
}

export function DiffSummary({ diff }: { diff: ImportPreview['diff'] }) {
  return (
    <Card title="Changes">
      {'rows_added' in diff ? <ScoresDiffView diff={diff} /> : <StationsDiffView diff={diff} />}
    </Card>
  );
}
