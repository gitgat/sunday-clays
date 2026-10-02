import { useMemo } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { AdminError } from '../../admin/components/AdminError';
import { allTime, bumpsKey, fetchBumps, todayIso, useBumps, type AnalyticsRange } from '../api';
import { analyticsExplainers } from '../explainers';
import { bumpsModel } from '../models';

const TITLE = 'Fist bumps per day';
const devices = (n: number) => `${String(n)} ${n === 1 ? 'device' : 'devices'}`;
const bumpCount = (n: number) => `${String(n)} ${n === 1 ? 'bump' : 'bumps'}`;

/** Bumps per day, how many devices bumped, and the most-bumped insights of the window. */
export function BumpsCard({ range }: { range: AnalyticsRange }) {
  const query = useBumps(range);
  // Fullscreen and the CSV run to today even when the window is custom and ends earlier.
  const today = todayIso();
  const fullQuery = useMemo<ChartFullQuery>(() => {
    const all = allTime(today);
    return {
      queryKey: [...bumpsKey(all), 'chart-full'],
      queryFn: async () => ({ ...bumpsModel(await fetchBumps(all)), note: 'Every day on record.' }),
    };
  }, [today]);

  if (query.isPending) {
    return (
      <Card title={TITLE}>
        <Skeleton label="Loading fist bumps" />
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
  const data = query.data;
  const model = bumpsModel(data);
  const summary = `${devices(data.devices)} bumped in this window · ${String(data.devices_all_time)} all time`;
  return (
    <>
      <ChartFrame
        title={TITLE}
        subtitle={summary}
        option={model.option}
        columns={model.columns}
        rows={model.rows}
        csvName={`fist-bumps-${range.asOf}`}
        ariaLabel={TITLE}
        urlKey="bumps"
        explainer={analyticsExplainers.bumps}
        fullQuery={fullQuery}
        emptyInline={
          model.rows.every((r) => r.bumps === 0) ? (
            <EmptyState title="Nothing counted in this window yet." />
          ) : undefined
        }
      />
      <Card title="Most-bumped insights">
        {data.top.length === 0 ? (
          <p className="text-sm text-text-muted">No bumps in this window yet.</p>
        ) : (
          <ol aria-label="Most-bumped insights" className="flex flex-col gap-2 text-sm">
            {data.top.map((t) => (
              <li key={t.key} className="flex min-w-0 justify-between gap-3">
                <span className="min-w-0 break-words">
                  {t.headline ?? 'An insight no longer on the site'}
                </span>
                <span className="shrink-0 text-text-muted">{bumpCount(t.bumps)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </>
  );
}
