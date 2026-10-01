import { lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { Stat } from '../../../components/ui/Stat';
import { filterRowsByWindow, type WindowRange } from '../../../lib/timeWindow';
import { useWindowEvents } from '../api';
import type { EventSummary } from '../api';
import { homeExplainers } from '../explainers';
import { formatDay, formatScore, round1 } from '../format';
import { turnout } from '../turnout';

// Code-split: ChartFrame and ECharts load after the season stats (and the rest of home) render.
const TurnoutChart = lazy(async () => ({
  default: (await import('./TurnoutChart')).TurnoutChart,
}));

/** Full-results Sundays are the results-complete ones (C7); turnout and the high use every scored Sunday. */
export function pulseStats(events: EventSummary[]) {
  const scored = events.filter((e) => e.has_scores);
  const tops = scored.flatMap((e) => (e.top_score === null ? [] : [e.top_score]));
  return {
    held: events.filter((e) => e.results_complete).length,
    scored: scored.length,
    avgTurnout:
      scored.length === 0
        ? null
        : round1(scored.map(turnout).reduce((a, b) => a + b, 0) / scored.length),
    seasonHigh: tops.length === 0 ? null : Math.max(...tops),
  };
}

/**
 * The club's numbers and the turnout chart for the 8 weeks up to the Sunday Sheet's issue. The
 * range is fixed: the header time window does not apply there.
 */
export function ClubPulse({ range }: { range: WindowRange }) {
  const { events, isPending, error } = useWindowEvents(range);
  const label = `8 weeks to ${formatDay(range.to)}`;
  const pulseCard = (body: ReactNode) => <Card title="Club pulse">{body}</Card>;

  if (isPending) return pulseCard(<Skeleton className="h-40" />);
  if (error !== null)
    return pulseCard(
      <EmptyState title="Couldn't load these Sundays" description={error.message} />,
    );
  const stats = pulseStats(filterRowsByWindow(events, 'event_date', range));
  const tag = `${label} · not affected by the time filter`;
  // The chart is a sibling card, not nested in the pulse card: nesting would cost its header
  // 32px on a phone and truncate the title beside the Table/CSV/Fullscreen buttons.
  // With no scored Sunday in the 8 weeks the pulse says so, and the chart still shows: its Table,
  // CSV and Fullscreen reach every Sunday on record (Home kept them), without widen buttons.
  return (
    <>
      <Card title="Club pulse" subtitle={tag}>
        {stats.scored === 0 ? (
          <EmptyState title="No scored Sundays in these 8 weeks" />
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <Stat
              label="Sundays with full results"
              value={String(stats.held)}
              explainer={homeExplainers.pulseHeldSheet}
            />
            <Stat
              label="Avg turnout"
              value={formatScore(stats.avgTurnout)}
              explainer={homeExplainers.pulseTurnoutSheet}
            />
            <Stat
              label="Highest score"
              value={formatScore(stats.seasonHigh)}
              explainer={homeExplainers.pulseHighSheet}
            />
          </div>
        )}
      </Card>
      <Suspense
        fallback={
          <Card>
            <Skeleton label="Loading the turnout chart" className="h-64" />
          </Card>
        }
      >
        <TurnoutChart
          events={events}
          range={range}
          label={label}
          explainer={homeExplainers.pulseSheet}
          windowName="these 8 weeks"
        />
      </Suspense>
    </>
  );
}
