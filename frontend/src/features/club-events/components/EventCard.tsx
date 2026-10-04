import { Link } from 'react-router';
import type { ClubEventSummary } from '../api';
import { deadlineLine, spotsLine, whenLine } from '../format';
import { MyChip } from './MyChip';

/** One upcoming club event in the list; the whole card opens the event (§5.7.2). */
export function EventCard({ event }: { event: ClubEventSummary }) {
  const deadline = deadlineLine(event);
  return (
    <Link
      to={`/club-events/${event.id}`}
      className="block rounded-card bg-elevated p-4 text-text shadow-sm hover:bg-surface"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="min-w-0 break-words text-base font-medium">{event.title}</h2>
        <div className="flex flex-wrap gap-2">
          {event.state === 'cancelled' && (
            <span className="rounded-button border border-outline-variant px-2 text-xs text-text-muted">
              Cancelled
            </span>
          )}
          {event.state !== 'cancelled' && <MyChip eventId={event.id} />}
        </div>
      </div>
      <p className="text-sm text-text-muted">{whenLine(event)}</p>
      <p className="text-sm">{spotsLine(event)}</p>
      {deadline !== null && <p className="text-sm text-text-muted">{deadline}</p>}
    </Link>
  );
}
