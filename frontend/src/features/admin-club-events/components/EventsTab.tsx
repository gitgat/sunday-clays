import { useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { AdminError } from '../../admin/components/AdminError';
import { useAdminClubEvents } from '../api';
import { sortEvents } from '../form';
import { EventEditor } from './EventEditor';
import { EventForm } from './EventForm';

/** Upcoming first (soonest), then past (most recent), each with its counts; one opens in the editor. */
export function EventsTab() {
  const events = useAdminClubEvents();
  const [now] = useState(() => Date.now());
  const [selected, setSelected] = useState<number | 'new' | null>(null);
  if (events.isError) return <AdminError error={events.error} />;
  if (events.data === undefined) return <Skeleton label="Loading club events" />;
  const sorted = sortEvents(events.data, now);
  const current = sorted.find((e) => e.id === selected);
  return (
    <div className="flex flex-col gap-4">
      <Button className="self-start" onClick={() => setSelected('new')}>
        New event
      </Button>
      {selected === 'new' && (
        <Card title="New club event">
          <EventForm event={null} onSaved={(id) => setSelected(id)} />
        </Card>
      )}
      {sorted.length === 0 ? (
        <EmptyState title="No club events yet." />
      ) : (
        <ul aria-label="Club events" className="flex flex-col">
          {sorted.map((event) => (
            <li key={event.id}>
              <button
                type="button"
                aria-pressed={event.id === selected}
                onClick={() => setSelected(event.id)}
                className="flex min-h-11 w-full flex-wrap items-center justify-between gap-2 border-t border-outline-variant py-2 text-left"
              >
                <span className="break-words font-medium">{event.title}</span>
                <span className="text-sm text-text-muted">
                  {`${event.local_date} · ${event.signups} going · ${event.waitlist_count} on the waitlist`}
                  {event.state === 'cancelled' ? ' · Cancelled' : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {current !== undefined && (
        <EventEditor key={current.id} event={current} onDeleted={() => setSelected(null)} />
      )}
    </div>
  );
}
