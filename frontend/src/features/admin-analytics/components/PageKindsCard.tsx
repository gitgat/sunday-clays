import { useMemo } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { AdminError } from '../../admin/components/AdminError';
import { allTime, fetchPages, pagesKey, todayIso, usePages, type AnalyticsRange } from '../api';
import { analyticsExplainers } from '../explainers';
import { pageKindsModel } from '../models';

const TITLE = 'Page views by page';

export function PageKindsCard({ range }: { range: AnalyticsRange }) {
  const query = usePages(range);
  // Fullscreen and the CSV run to today even when the window is custom and ends earlier.
  const today = todayIso();
  const fullQuery = useMemo<ChartFullQuery>(() => {
    const all = allTime(today);
    return {
      queryKey: [...pagesKey(all), 'chart-full'],
      queryFn: async () => ({
        ...pageKindsModel(await fetchPages(all)),
        note: 'Every day on record.',
      }),
    };
  }, [today]);

  if (query.isPending) {
    return (
      <Card title={TITLE}>
        <Skeleton label="Loading page views" />
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
  const model = pageKindsModel(query.data);
  return (
    <ChartFrame
      title={TITLE}
      subtitle="Counted views of each kind of page"
      option={model.option}
      columns={model.columns}
      rows={model.rows}
      csvName={`page-views-${range.asOf}`}
      ariaLabel={TITLE}
      urlKey="pages"
      explainer={analyticsExplainers.pages}
      fullQuery={fullQuery}
      emptyInline={
        query.data.length === 0 ? (
          <EmptyState title="Nothing counted in this window yet." />
        ) : undefined
      }
      height={Math.max(240, 40 * model.rows.length)}
    />
  );
}
