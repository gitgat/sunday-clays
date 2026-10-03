import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { Stat } from '../../../components/ui/Stat';
import { isSpecial, specialLine, targetsOf } from '../../events/format';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { useEventDetail, useMeta } from '../api';
import type { EventDetail } from '../api';
import { homeExplainers } from '../explainers';
import { formatDay, formatScore } from '../format';

export function winners(results: EventDetail['results']): string[] {
  return results
    .filter((r) => r.is_best_round && r.event_rank === 1)
    .map((r) => r.display_name)
    .sort((a, b) => a.localeCompare(b));
}

export function attendanceText(headCount: number | null): string {
  return headCount === null
    ? 'No scores recorded'
    : `Attendance only — ${headCount} shooters, no scores recorded`;
}

/** A special shoot: its tag and label, the best score of its total; no Median or Top score (not ranked). */
function SpecialLatest({ event }: { event: EventDetail }) {
  const total = targetsOf(event);
  const max = Math.max(...event.results.filter((r) => r.is_best_round).map((r) => r.score));
  const names = event.results
    .filter((r) => r.is_best_round && r.score === max)
    .map((r) => r.display_name)
    .sort((a, b) => a.localeCompare(b));
  return (
    <>
      <p className="text-text-muted">{specialLine(event)}</p>
      {names.length > 0 && <p>{`Top score: ${names.join(' & ')} — ${max} of ${total}`}</p>}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat
          label="Shooters"
          value={String(event.n_shooters)}
          explainer={homeExplainers.latestShooters}
        />
      </div>
      <p className="text-sm text-text-muted">
        Special shoots are not ranked or rated, so there is no median here.
      </p>
    </>
  );
}

function LatestEventBody({
  event,
  lastFull,
}: {
  event: EventDetail;
  /**
   * The latest Sunday with scores (GET /api/meta), for an attendance-only Sunday to point at.
   * Any round type: /api/meta has no round-type-filtered date, and a second request is not worth
   * a link. With a round-type filter it can point at a Sunday of another type.
   */
  lastFull: string | null;
}) {
  const top = winners(event.results);
  const special = isSpecial(event);
  const eventLink = useRoundTypeLink(`/events/${event.event_date}`);
  const fullLink = useRoundTypeLink(`/events/${lastFull ?? event.event_date}`);
  return (
    <div className="flex flex-col gap-3">
      <Link
        to={eventLink}
        className="inline-flex min-h-11 items-center self-start text-lg font-medium"
      >
        {formatDay(event.event_date)}
      </Link>
      {special && event.has_scores ? (
        <SpecialLatest event={event} />
      ) : event.has_scores ? (
        <>
          {/* No rank-1 best round (metrics not computed yet): no names to show; Top score below. */}
          {top.length > 0 && (
            <p>{`${top.length > 1 ? 'Winners' : 'Winner'}: ${top.join(' & ')} — ${formatScore(event.top_score)}`}</p>
          )}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Stat
              label="Shooters"
              value={String(event.n_shooters)}
              explainer={homeExplainers.latestShooters}
            />
            <Stat
              label="Median"
              value={formatScore(event.median)}
              explainer={homeExplainers.latestMedian}
            />
            <Stat
              label="Top score"
              value={formatScore(event.top_score)}
              explainer={homeExplainers.latestTop}
            />
          </div>
        </>
      ) : (
        <>
          <p>{attendanceText(event.head_count)}</p>
          {lastFull !== null && (
            <Link to={fullLink} className="inline-flex min-h-11 items-center self-start underline">
              {`Latest full results: ${formatDay(lastFull)}`}
            </Link>
          )}
        </>
      )}
      {event.has_scores && (
        <Link to={eventLink} className="inline-flex min-h-11 items-center self-start underline">
          Full results
        </Link>
      )}
    </div>
  );
}

export function LatestEventCard() {
  const meta = useMeta();
  const date = meta.data?.last_event_date ?? null;
  const event = useEventDetail(date);

  function body(): ReactNode {
    if (meta.isPending) return <Skeleton className="h-32" />;
    if (meta.isError)
      return (
        <EmptyState title="Couldn't load the latest Sunday" description={meta.error.message} />
      );
    if (date === null)
      return (
        <EmptyState title="No Sundays yet" description="An admin can upload the scores workbook." />
      );
    if (event.isPending) return <Skeleton className="h-32" />;
    if (event.isError)
      return (
        <EmptyState title="Couldn't load the latest Sunday" description={event.error.message} />
      );
    return <LatestEventBody event={event.data} lastFull={meta.data?.last_score_date ?? null} />;
  }

  return (
    <Card title="Latest Sunday" subtitle="Not affected by the time filter" tour="sunday">
      {body()}
    </Card>
  );
}
