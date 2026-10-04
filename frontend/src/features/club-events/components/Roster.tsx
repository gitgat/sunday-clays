import { Link } from 'react-router';
import type { ClubEventDetail, RosterRow } from '../api';
import { EMPTY_ROSTER, PURGED, rosterSummary } from '../format';

function Row({
  row,
  mine,
  canCancel,
  onCancel,
}: {
  row: RosterRow;
  mine: boolean;
  canCancel: boolean;
  onCancel: (row: RosterRow) => void;
}) {
  return (
    <li className="flex min-h-11 flex-wrap items-center gap-2 break-words border-b border-outline-variant py-1">
      {row.waitlist_position !== null && (
        <span className="w-6 text-text-muted">{row.waitlist_position}.</span>
      )}
      <span className="min-w-0 flex-1 break-words">
        {row.shooter_id !== null ? (
          <Link
            to={`/shooters/${row.shooter_id}`}
            className="inline-flex min-h-11 min-w-0 items-center break-words underline"
          >
            {row.name}
          </Link>
        ) : (
          row.name
        )}
      </span>
      {row.guests > 0 && (
        <span className="rounded-button border border-outline-variant px-2 text-xs">
          +{row.guests}
        </span>
      )}
      {mine && <span className="rounded-button border border-accent px-2 text-xs">You</span>}
      {canCancel && (
        <button
          type="button"
          aria-label={`Cancel ${row.name}'s spot`}
          onClick={() => onCancel(row)}
          className="inline-flex min-h-11 min-w-11 items-center justify-center px-2 text-sm text-text-muted underline hover:text-text"
        >
          Cancel
        </button>
      )}
    </li>
  );
}

/** Who's coming: going rows, then the numbered waitlist. Never in a shared image (§5.7.3). */
export function Roster({
  event,
  mine,
  onCancel,
}: {
  event: ClubEventDetail;
  mine: ReadonlySet<number>;
  onCancel: (row: RosterRow) => void;
}) {
  if (event.purged) return <p className="text-sm text-text-muted">{PURGED}</p>;
  if (event.roster.length === 0) return <p className="text-sm text-text-muted">{EMPTY_ROSTER}</p>;
  const canCancel = event.state !== 'started' && event.upcoming;
  const going = event.roster.filter((r) => r.status === 'going');
  const waiting = event.roster.filter((r) => r.status === 'waitlist');
  const item = (row: RosterRow) => (
    <Row
      key={row.registration_id}
      row={row}
      mine={mine.has(row.registration_id)}
      canCancel={canCancel}
      onCancel={onCancel}
    />
  );
  return (
    <div data-share-exclude="" className="flex flex-col gap-2">
      <ul aria-label="Going">{going.map(item)}</ul>
      {waiting.length > 0 && (
        <>
          <h3 className="mt-2 text-sm font-medium">Waitlist</h3>
          <ul aria-label="Waitlist">{waiting.map(item)}</ul>
        </>
      )}
      <p className="text-sm text-text-muted">{rosterSummary(event)}</p>
    </div>
  );
}
