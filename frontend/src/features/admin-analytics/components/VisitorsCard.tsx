import { useMemo, useState } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { Chip } from '../../../components/ui/Chip';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatDate } from '../../../lib/format';
import { AdminError } from '../../admin/components/AdminError';
import { allTime, fetchVisitors, useVisitors, visitorsKey, type AnalyticsRange } from '../api';
import { analyticsExplainers } from '../explainers';
import { visitorsModel, type Per } from '../models';

const TITLE = 'Visitors';
const plural = (n: number) => `${String(n)} ${n === 1 ? 'device' : 'devices'}`;

/** Unique devices per day or week (switchable), and the busiest days of the window. */
export function VisitorsCard({ range }: { range: AnalyticsRange }) {
  const [per, setPer] = useState<Per>('day');
  const query = useVisitors(range);
  const fullQuery = useMemo<ChartFullQuery>(() => {
    const all = allTime(range.asOf);
    return {
      queryKey: [...visitorsKey(all), per, 'chart-full'],
      queryFn: async () => ({
        ...visitorsModel(await fetchVisitors(all), per),
        note: per === 'day' ? 'Every day on record.' : 'Every week on record.',
      }),
    };
  }, [range.asOf, per]);

  if (query.isPending) {
    return (
      <Card title={TITLE}>
        <Skeleton label="Loading visitors" />
      </Card>
    );
  }
  if (query.isError) {
    return (
      <Card title={TITLE}>
        <AdminError error={query.error} />
      </Card>
    );
  }
  const model = visitorsModel(query.data, per);
  if (query.data.days.every((d) => d.devices === 0)) {
    return (
      <Card title={TITLE}>
        <EmptyState title="Nothing counted in this window yet." />
      </Card>
    );
  }
  return (
    <>
      <ChartFrame
        title={TITLE}
        subtitle={per === 'day' ? 'Different devices each day' : 'Different devices each week'}
        option={model.option}
        columns={model.columns}
        rows={model.rows}
        csvName={`visitors-${per}-${range.asOf}`}
        ariaLabel={`Visitors per ${per}`}
        urlKey="visitors"
        explainer={analyticsExplainers.visitors}
        fullQuery={fullQuery}
        controls={
          <>
            <Chip selected={per === 'day'} onClick={() => setPer('day')}>
              Per day
            </Chip>
            <Chip selected={per === 'week'} onClick={() => setPer('week')}>
              Per week
            </Chip>
          </>
        }
      />
      <Card title="Busiest days">
        {query.data.busiest.length === 0 ? (
          <p className="text-sm text-text-muted">No visits in this window yet.</p>
        ) : (
          <ol aria-label="Busiest days" className="flex flex-col gap-2 text-sm">
            {query.data.busiest.map((d) => (
              <li key={d.day} className="flex min-w-0 justify-between gap-3">
                <span>{formatDate(d.day)}</span>
                <span className="text-text-muted">{plural(d.devices)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </>
  );
}
