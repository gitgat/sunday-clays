import { useId } from 'react';
import { Card } from '../../../components/ui/Card';
import type { ImportPreview, ScoresDiff, SpecialDiff, StationsDiff } from '../api';
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

/** New names and possible duplicates, shared by the scores and special-shoot previews. */
function NameHints({
  newNames,
  duplicates,
}: {
  newNames: string[];
  duplicates: ScoresDiff['possible_duplicates'];
}) {
  return (
    <>
      {newNames.length > 0 && (
        <details>
          <summary className="min-h-11 cursor-pointer py-2.5">{`New names (${newNames.length})`}</summary>
          <ul className="flex flex-col">
            {newNames.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      )}
      {duplicates.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="font-medium">Possible duplicates</h3>
          <ul className="flex flex-col">
            {duplicates.map(([a, b]) => (
              <li key={`${a}|${b}`}>{`${a} ↔ ${b}`}</li>
            ))}
          </ul>
          <p className="text-xs text-text-muted">
            New names are new shooters; merge real duplicates later under Identity.
          </p>
        </div>
      )}
    </>
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
      <NameHints newNames={diff.new_names} duplicates={diff.possible_duplicates} />
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

/** Decision 13: weekly-workbook rows on the special Sunday are left out while it is live. */
function weeklyRowsNote(diff: SpecialDiff): string {
  const rows = diff.regular_rows_on_date === 1 ? '1 row' : `${diff.regular_rows_on_date} rows`;
  return `The scores workbook has ${rows} on ${formatDay(diff.event_date)}. While this special shoot is live they are left out, and rolling it back brings them back.`;
}

function SpecialDiffView({ diff }: { diff: SpecialDiff }) {
  return (
    <div className="flex flex-col gap-3">
      {diff.regular_rows_on_date > 0 && (
        <p role="note" className="rounded-card border-2 border-error-container p-3">
          {weeklyRowsNote(diff)}
        </p>
      )}
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Row label="Sunday" value={formatDay(diff.event_date)} />
        <Row label="Special shoot" value={diff.label} />
        <Row label="Targets" value={`${diff.target_total} (${diff.stations.length} stations)`} />
        <Row label="Shooters" value={String(diff.n_shooters)} />
        <Row
          label="Replaces"
          value={diff.replaces_import === null ? '—' : `Import #${diff.replaces_import}`}
        />
      </dl>
      <NameHints newNames={diff.new_names} duplicates={diff.possible_duplicates} />
    </div>
  );
}

export function DiffSummary({ diff }: { diff: ImportPreview['diff'] }) {
  return (
    <Card title="Changes">
      {'rows_added' in diff ? (
        <ScoresDiffView diff={diff} />
      ) : 'events_replaced' in diff ? (
        <StationsDiffView diff={diff} />
      ) : (
        <SpecialDiffView diff={diff} />
      )}
    </Card>
  );
}
