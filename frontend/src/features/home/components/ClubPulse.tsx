import { lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { Stat } from '../../../components/ui/Stat';
import { useTimeWindow, filterRowsByWindow } from '../../../lib/timeWindow';
import { windowTagText } from '../../../lib/windowText';
import { useWindowEvents } from '../api';
import type { EventSummary } from '../api';
import { homeExplainers } from '../explainers';
import { formatScore, round1 } from '../format';
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

export function ClubPulse() {
  const { window, range, label } = useTimeWindow();
  const { events, isPending, error } = useWindowEvents();
  const pulseCard = (body: ReactNode) => <Card title="Club pulse">{body}</Card>;

  if (isPending) return pulseCard(<Skeleton className="h-40" />);
  // A failed meta leaves the range null too; the latest-Sunday card beside this one shows that error.
  if (range === null) return pulseCard(<EmptyState title="No scored Sundays yet" />);
  if (error !== null)
    return pulseCard(
      <EmptyState title="Couldn't load these Sundays" description={error.message} />,
    );
  const stats = pulseStats(filterRowsByWindow(events, 'event_date', range));
  const tag = windowTagText(window, range);
  const chart = (
    <Suspense
      fallback={
        <Card>
          <Skeleton label="Loading the turnout chart" className="h-64" />
        </Card>
      }
    >
      <TurnoutChart events={events} range={range} label={label} />
    </Suspense>
  );
  // An empty window shows the chart card alone, so there is one message: its Table, CSV and
  // Fullscreen still reach every Sunday, and it offers 12M and All instead of falling back to
  // all-time numbers under this tag.
  if (stats.scored === 0) return chart;
  // The chart is a sibling card, not nested in the pulse card: nesting would cost its header
  // 32px on a phone and truncate the title beside the Table/CSV/Fullscreen buttons.
  return (
    <>
      <Card title="Club pulse" subtitle={tag}>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Stat
            label="Sundays with full results"
            value={String(stats.held)}
            explainer={homeExplainers.pulseHeld}
          />
          <Stat
            label="Avg turnout"
            value={formatScore(stats.avgTurnout)}
            explainer={homeExplainers.pulseTurnout}
          />
          <Stat
            label="Highest score"
            value={formatScore(stats.seasonHigh)}
            explainer={homeExplainers.pulseHigh}
          />
        </div>
      </Card>
      {chart}
    </>
  );
}
