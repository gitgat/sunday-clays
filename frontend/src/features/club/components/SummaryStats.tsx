import { Skeleton } from '../../../components/ui/Skeleton';
import { Stat } from '../../../components/ui/Stat';
import { useMeta, useTimeWindow } from '../../../lib/timeWindow';
import { windowPhrase, windowTagText } from '../../../lib/windowText';
import { useClubSummary } from '../api';
import { explainers } from '../explainers';
import { formatDay } from '../format';

/**
 * Header stats over the time window, tagged with its name and dates. On error they are omitted
 * (the member-status chart shows the summary error). An empty window says so in plain words.
 */
export function SummaryStats() {
  const { window, range } = useTimeWindow();
  const meta = useMeta();
  const query = useClubSummary(range);
  if (range === null) return meta.isPending ? <Skeleton className="h-20" /> : null;
  if (query.isPending) return <Skeleton className="h-20" />;
  if (query.isError) return null;
  const s = query.data;
  const count = (n: number) => n.toLocaleString('en-US');
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-text-muted">{windowTagText(window, range)}</p>
      {s.n_rounds === 0 ? (
        <p className="text-text-muted">
          {`No scored Sundays in ${windowPhrase(window, range)}. Pick a longer window (12M or All) above.`}
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Stat
            label="Sundays with full results"
            value={count(s.n_held_events)}
            explainer={explainers['stat-sundays']}
          />
          <Stat
            label="Shooters"
            value={count(s.n_shooters)}
            explainer={explainers['stat-shooters']}
          />
          <Stat label="Rounds" value={count(s.n_rounds)} explainer={explainers['stat-rounds']} />
          <Stat
            label="Clays broken"
            value={count(s.clays_broken)}
            explainer={explainers['stat-clays']}
          />
          <Stat
            label="First scored Sunday"
            value={s.first_event === null ? '—' : formatDay(s.first_event)}
            explainer={explainers['stat-first']}
          />
        </div>
      )}
    </div>
  );
}
