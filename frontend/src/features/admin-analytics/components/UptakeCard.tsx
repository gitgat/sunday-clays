import { useMemo } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatDate } from '../../../lib/format';
import { AdminError } from '../../admin/components/AdminError';
import {
  allTime,
  fetchUptake,
  uptakeKey,
  useUptake,
  type AnalyticsRange,
  type Uptake,
} from '../api';
import { analyticsExplainers } from '../explainers';
import { uptakeModel } from '../models';

const TITLE = '“Which one are you?” answers';

function summary(data: Uptake): string {
  if (data.latest_since === null) return 'No visits in this window are kept in detail.';
  const { picked, skipped, none } = data.latest;
  return `Last answer of each device since ${formatDate(data.latest_since)}: ${String(picked)} picked a name, ${String(skipped)} skipped, ${String(none)} not answered`;
}

/** Answers per week (stacked), with each device's last answer across the window above. */
export function UptakeCard({ range }: { range: AnalyticsRange }) {
  const query = useUptake(range);
  const fullQuery = useMemo<ChartFullQuery>(() => {
    const all = allTime(range.asOf);
    return {
      queryKey: [...uptakeKey(all), 'chart-full'],
      queryFn: async () => ({
        ...uptakeModel(await fetchUptake(all)),
        note: 'Every week on record.',
      }),
    };
  }, [range.asOf]);

  if (query.isPending) {
    return (
      <Card title={TITLE}>
        <Skeleton label="Loading answers" />
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
  const model = uptakeModel(query.data);
  if (query.data.weeks.every((w) => w.picked + w.skipped + w.none === 0)) {
    return (
      <Card title={TITLE} subtitle={summary(query.data)}>
        <EmptyState title="Nothing counted in this window yet." />
      </Card>
    );
  }
  return (
    <ChartFrame
      title={TITLE}
      subtitle={summary(query.data)}
      option={model.option}
      columns={model.columns}
      rows={model.rows}
      csvName={`which-one-are-you-${range.asOf}`}
      ariaLabel="Which one are you? answers per week"
      urlKey="uptake"
      explainer={analyticsExplainers.uptake}
      fullQuery={fullQuery}
    />
  );
}
