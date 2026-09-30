import { useMemo } from 'react';

import { barOption } from '../../../components/charts/builders/bar';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { shooterLabels, useChartTarget } from '../../../components/charts/chartTarget';
import type {
  ChartFull,
  TabularColumn,
  TabularData,
  TabularRow,
} from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatDate } from '../../../lib/format';
import { rangeText } from '../../../lib/windowText';
import { useMeta, useTimeWindow } from '../../../lib/timeWindow';
import { datesText, windowInWords } from '../../competition/windowText';
import { type ClimberOut, type ShooterStatus, useRatingMovers } from '../api';
import { explainers } from '../explainers';
import { boardWindow } from '../labels';

const TITLE = 'Biggest rating gains';
const CHART_TOP = 10;
const hlLabels = shooterLabels('display_name');

const COLUMNS: TabularColumn[] = [
  { key: 'display_name', label: 'Shooter', type: 'string' },
  { key: 'gain', label: 'Rating points gained', type: 'number' },
  { key: 'n_rounds', label: 'Rounds in the window', type: 'int' },
];

/** One bar per climber; a name two shooters share is charted as `<name> #<id>` (as `chartRows`). */
export function moversModel(climbers: readonly ClimberOut[]): TabularData {
  const names = climbers.map((c) => c.display_name);
  const rows: TabularRow[] = climbers.map((c) => ({
    shooter_id: c.shooter_id,
    display_name:
      names.indexOf(c.display_name) === names.lastIndexOf(c.display_name)
        ? c.display_name
        : `${c.display_name} #${String(c.shooter_id)}`,
    gain: c.gain,
    n_rounds: c.n_rounds,
  }));
  return { columns: COLUMNS, rows };
}

const barsFor = (data: TabularData) =>
  barOption(data, { x: 'display_name', y: ['gain'], horizontal: true });

/**
 * Plan 12 `lb-movers`: the biggest rating gains over the header window, climbers only (never a
 * rating ranking). `asOf` is the leaderboards page's "Board as of" date; an insight link's own
 * dates (`lb-movers.from/.to`) win over the window.
 */
export function MoversChart({
  asOf,
  status = null,
}: {
  asOf: string | null;
  status?: ShooterStatus | null;
}) {
  const { target } = useChartTarget('lb-movers');
  const { window } = useTimeWindow();
  const latest = useMeta().data?.last_score_date ?? null;
  const asked = target.window
    ? { period: 'season' as const, since: target.window.from, asOf: target.window.to }
    : boardWindow(window, asOf, latest);
  const query = useRatingMovers({
    period: asked?.period ?? 'season',
    since: asked?.since ?? null,
    asOf: asked?.asOf ?? null,
    status,
    enabled: asked !== null,
  });
  const everyone = useMemo(() => moversModel(query.data?.rows ?? []), [query.data]);
  // The first ten climbers, plus any highlighted climber further down so the ring shows inline.
  const top = useMemo<TabularData>(() => {
    const ringed = new Set(target.hl.filter((k) => k.startsWith('s:')).map((k) => k.slice(2)));
    const rows = everyone.rows.filter((r, i) => i < CHART_TOP || ringed.has(String(r.shooter_id)));
    return { columns: COLUMNS, rows };
  }, [everyone, target.hl]);
  const option = useMemo(() => barsFor(top), [top]);
  // Fullscreen and the CSV: every climber, not the first ten.
  const full = useMemo<ChartFull>(
    () => ({
      option: barsFor(everyone),
      rows: everyone.rows,
      height: Math.max(320, 80 + 28 * everyone.rows.length),
      note: 'Everyone who gained rating in this window.',
      scope: 'windowed',
    }),
    [everyone],
  );
  const where = target.window ? rangeText(target.window) : windowInWords(window);
  if (query.isError) {
    return (
      <Card title={TITLE} id="chart-lb-movers">
        <p className="text-text-muted">Couldn’t load the rating gains.</p>
      </Card>
    );
  }
  if (asked === null) return null; // the page's own skeleton covers a window that cannot be dated yet
  if (query.data === undefined) return <Skeleton className="h-64" />;
  if (everyone.rows.length === 0) {
    return (
      <Card title={TITLE} id="chart-lb-movers">
        <p className="text-text-muted">No rating gains to show for {where} yet.</p>
      </Card>
    );
  }
  const { start, end } = query.data;
  const dates =
    start === null || start === undefined
      ? `all time, to ${formatDate(end)}`
      : datesText(start, end, latest);
  return (
    <ChartFrame
      title={TITLE}
      subtitle={`Rating points gained, ${dates}`}
      option={option}
      columns={everyone.columns}
      rows={top.rows}
      full={full}
      csvName="rating-gains"
      ariaLabel="Rating points gained by the biggest climbers"
      urlKey="lb-movers"
      explainer={explainers['lb-movers']}
      hlLabels={hlLabels}
    />
  );
}
