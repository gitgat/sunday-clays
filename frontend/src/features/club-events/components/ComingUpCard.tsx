import { Link } from 'react-router';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { Card } from '../../../components/ui/Card';
import { useFeature } from '../../../lib/features';
import { useClubEvents } from '../api';
import { deadlineLine, formatEventDate, spotsLine, whenLine } from '../format';
import { useDeviceSignups } from '../tokens';
import { MyChip } from './MyChip';

/**
 * Home "Coming up" (§5.7.4): the next club event, in the main column after Next Sunday, so it can
 * only push content below it. Renders nothing (and asks nothing) for a viewer while the switch is
 * off, and nothing when no club event is coming up. The list query is cached for a minute.
 */
export function ComingUpCard() {
  const feature = useFeature('events');
  const events = useClubEvents({ enabled: feature.visible });
  const signups = useDeviceSignups();
  if (!feature.visible || events.data === undefined) return null;
  const upcoming = events.data.upcoming;
  const next = upcoming.find((e) => e.state !== 'cancelled');
  const lost = upcoming.find(
    (e) => e.state === 'cancelled' && signups.some((s) => s.eventId === e.id),
  );
  // §5.7.4: only when a non-cancelled upcoming event exists; the cancelled line rides on that card.
  if (next === undefined) return null;
  const signedUp = signups.some((s) => s.eventId === next.id);
  return (
    <Card title="Coming up" actions={<AdminPreviewBadge feature="events" />}>
      <div className="flex flex-col gap-1">
        {lost !== undefined && (
          <p role="note" className="font-medium">
            {`${lost.title} on ${formatEventDate(lost.local_date)} was cancelled.`}
          </p>
        )}
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
