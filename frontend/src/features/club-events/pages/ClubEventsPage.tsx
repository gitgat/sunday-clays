import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { ApiError } from '../../../api/errors';
import { FEATURES_QUERY_KEY } from '../../../lib/features';
import { useClubEvents } from '../api';
import { EventCard } from '../components/EventCard';
import { cameLine, formatEventDate } from '../format';
import { readPastOpen, writePastOpen } from '../tokens';

/** /club-events (§5.7.2): upcoming cards, past events collapsed. No filters (D12). */
export function ClubEventsPage() {
  const events = useClubEvents();
  const qc = useQueryClient();
  useEffect(() => {
    // The gate's 404: the switch went off while this page was open, so refetch the switches.
    if (events.error instanceof ApiError && events.error.code === 'http_404') {
      void qc.invalidateQueries({ queryKey: FEATURES_QUERY_KEY });
    }
  }, [events.error, qc]);
  const [pastOpen, setPastOpen] = useState(readPastOpen);
  const toggle = () => {
    writePastOpen(!pastOpen);
    setPastOpen(!pastOpen);
  };
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-bold">Club events</h1>
        <AdminPreviewBadge feature="events" />
      </div>
      <p className="text-text-muted">
        Club get-togethers beyond Sunday shoots. Sign up so organizers know who's coming.
      </p>
      {events.isPending ? (
        <Skeleton label="Loading club events" />
      ) : events.data === undefined ? (
        <EmptyState title="Club events aren't available right now." />
      ) : (
        <>
          {events.data.upcoming.length === 0 ? (
            <EmptyState title="No club events coming up. Check back soon." />
          ) : (
            <ul className="flex flex-col gap-3">
              {events.data.upcoming.map((event) => (
                <li key={event.id}>
                  <EventCard event={event} />
                </li>
              ))}
            </ul>
          )}
          {events.data.past.length > 0 && (
            <section className="flex flex-col gap-2">
              <button
                type="button"
                aria-expanded={pastOpen}
                onClick={toggle}
                className="inline-flex min-h-11 items-center self-start text-text-muted underline"
              >
                Past events ({events.data.past.length})
              </button>
              {pastOpen && (
                <ul className="flex flex-col">
                  {events.data.past.map((event) => (
                    <li
                      key={event.id}
                      className="flex min-h-11 flex-wrap items-center justify-between gap-2 border-b border-outline-variant"
                    >
                      <Link
                        to={`/club-events/${event.id}`}
                        className="min-w-0 break-words underline"
                      >
                        {event.title}
                      </Link>
                      <span className="text-sm text-text-muted">
                        {formatEventDate(event.local_date)} ·{' '}
                        {event.state === 'cancelled' ? 'Cancelled' : cameLine(event)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
