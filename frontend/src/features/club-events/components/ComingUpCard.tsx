import { useEffect } from 'react';
import { Link } from 'react-router';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { Card } from '../../../components/ui/Card';
import { useFeature } from '../../../lib/features';
import { useClubEvents, type ClubEventSummary } from '../api';
import { deadlineLine, formatEventDate, spotsLine, whenLine } from '../format';
import { pruneToList } from '../tokens';
import { MyChip } from './MyChip';
import { useMyRow } from './useMyRow';

/**
 * Home "Coming up" (§5.7.4): the next club event, in the main column after Next Sunday, so it can
 * only push content below it. Renders nothing (and asks nothing) for a viewer while the switch is
 * off, and nothing when no club event is coming up. The list query is cached for a minute.
 */
export function ComingUpCard() {
  const feature = useFeature('events');
  const events = useClubEvents({ enabled: feature.visible });
  const list = events.data;
  // Only a list fetched since mount: a cached one may predate an event this device just joined.
  const fresh = events.isFetchedAfterMount && !events.isFetching;
  useEffect(() => {
    if (feature.visible && fresh && list !== undefined) pruneToList(list);
  }, [feature.visible, fresh, list]);
  if (!feature.visible || list === undefined) return null;
  const upcoming = list.upcoming;
  const next = upcoming.find((e) => e.state !== 'cancelled');
  // §5.7.4: only when a non-cancelled upcoming event exists; the cancelled line rides on that card.
  if (next === undefined) return null;
  return <Next next={next} cancelled={upcoming.filter((e) => e.state === 'cancelled')} />;
}

function CancelledLine({ event }: { event: ClubEventSummary }) {
  const { row } = useMyRow(event.id);
  if (row === undefined) return null; // only for an event this device is still on the roster of
  return (
    <p role="note" className="font-medium">
      {`${event.title} on ${formatEventDate(event.local_date)} was cancelled.`}
    </p>
  );
}

function Next({ next, cancelled }: { next: ClubEventSummary; cancelled: ClubEventSummary[] }) {
  const { mine, row, pending } = useMyRow(next.id);
  // the roster decides; while it loads, a held token stands in so the link does not flip
  const signedUp = row !== undefined || (pending && mine.length > 0);
  return (
    <Card title="Coming up" actions={<AdminPreviewBadge feature="events" />}>
      <div className="flex flex-col gap-1">
        {cancelled.slice(0, 1).map((e) => (
          <CancelledLine key={e.id} event={e} />
        ))}
        <div className="flex flex-wrap items-center gap-2">
          <p className="min-w-0 break-words font-medium">{next.title}</p>
          <MyChip eventId={next.id} />
        </div>
        <p className="text-sm text-text-muted">{whenLine(next)}</p>
        <p className="text-sm">{spotsLine(next)}</p>
        {deadlineLine(next) !== null && (
          <p className="text-sm text-text-muted">{deadlineLine(next)}</p>
        )}
        <Link
          to={`/club-events/${next.id}`}
          className="mt-2 inline-flex min-h-11 items-center self-start rounded-button bg-primary px-4 text-sm font-medium text-text"
        >
          {next.state === 'open' && !signedUp ? 'Sign up' : 'See details'}
        </Link>
      </div>
    </Card>
  );
}
