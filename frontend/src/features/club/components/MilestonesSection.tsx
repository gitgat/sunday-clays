import { useId } from 'react';
import { Link } from 'react-router';
import { AboutBlock } from '../../../components/ui/AboutBlock';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { Card, CardHeadingLevel } from '../../../components/ui/Card';
import { useFeature } from '../../../lib/features';
import { formatDay } from '../../home/format';
import { useClubMilestones, type ClubMilestones } from '../api';
import { explainers } from '../explainers';
import { METRIC_CHIPS } from '../milestones';
import { LazyChart } from './LazyChart';

// ChartFrame pulls in ECharts, so the chart loads in its own chunk like the Club page's others.
const loadTotals = () => import('./TotalsChart');

function MilestoneList({ data }: { data: ClubMilestones | undefined }) {
  return (
    <Card title="Club milestones">
      <AboutBlock explainer={explainers['club-milestones']} label="About club milestones" />
      {data === undefined ? (
        <p role="status">Loading milestones…</p>
      ) : data.milestones.length === 0 ? (
        <p>No milestones yet.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {METRIC_CHIPS.map(({ value, label }) => {
            const rows = data.milestones.filter((m) => m.metric === value);
            if (rows.length === 0) return null;
            return (
              <section
                key={value}
                aria-labelledby={`milestones-${value}`}
                className="flex flex-col gap-1"
              >
                <h4 id={`milestones-${value}`} className="text-sm font-medium text-text-muted">
                  {label}
                </h4>
                <ul className="flex flex-col">
                  {rows.map((m) => (
                    <li key={`${m.metric}-${String(m.threshold)}`} className="flex flex-col">
                      <Link
                        to={`/events/${m.event_date}`}
                        className="inline-flex min-h-11 items-center underline"
                      >
                        {`${m.label} — ${formatDay(m.event_date)}`}
                      </Link>
                      {m.first_on_record && (
                        <span className="text-xs text-text-muted">
                          On the first Sunday on record
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/** The Club page's first section (Plan 19 §3.5.3); nothing at all for a viewer while off. */
export function MilestonesSection() {
  const { visible } = useFeature('club_milestones');
  const query = useClubMilestones(visible);
  const headingId = useId();
  if (!visible) return null;
  return (
    <section
      id="milestones"
      aria-labelledby={headingId}
      className="flex scroll-mt-28 flex-col gap-3"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 id={headingId} className="text-xl font-medium">
          Milestones
        </h2>
        <AdminPreviewBadge feature="club_milestones" />
      </div>
      <CardHeadingLevel value={3}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <MilestoneList data={query.data} />
          {query.data !== undefined && query.data.series.length > 0 && (
            <LazyChart title="Club totals over time" load={loadTotals} />
          )}
        </div>
      </CardHeadingLevel>
    </section>
  );
}
