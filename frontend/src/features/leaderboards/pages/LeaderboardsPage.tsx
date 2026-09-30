import { useMemo } from 'react';

import { PageTopSlot } from '../../../components/layout/pageTop';
import { barOption } from '../../../components/charts/builders/bar';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { useChartTarget, useScrollToTarget } from '../../../components/charts/chartTarget';
import type { ChartFull, TabularData } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { Chip } from '../../../components/ui/Chip';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useRoundTypes } from '../../../lib/roundTypes';
import {
  isCustomWindow,
  useMeta,
  usePageDefaultWindow,
  useTimeWindow,
  WINDOW_LABELS,
} from '../../../lib/timeWindow';
import { useLegacyParams } from '../../../lib/useLegacyParams';
import { useUrlState } from '../../../lib/useUrlState';
import { convertLegacyBoard } from '../../competition/legacyParams';
import { WidenWindow } from '../../competition/WidenWindow';
import { datesText, sundaysNote, THIN_SUNDAYS, windowInWords } from '../../competition/windowText';
import {
  type LeaderboardMetric,
  type LeaderboardOut,
  type ShooterStatus,
  useLeaderboard,
} from '../api';
import { boardExplainer } from '../explainers';
import { MoversChart } from '../components/MoversChart';
import { StandingsTable } from '../components/StandingsTable';
import { TimeMachine } from '../components/TimeMachine';
import {
  GAUGES,
  METRICS,
  RATING_METRICS,
  STATUSES,
  boardWindow,
  chartRows,
  formatEventDate,
  metricLabel,
  oneOf,
  optionalDate,
  optionalOneOf,
} from '../labels';

const METRIC_CODEC = oneOf(
  METRICS.map((m) => m.value),
  'avg_score',
);
const GAUGE_CODEC = optionalOneOf(GAUGES.map((g) => g.value));
const STATUS_CODEC = optionalOneOf(STATUSES.map((s) => s.value));
const CHART_TOP = 10;

/** `undefined` (not null) when one round is enough: EmptyState renders its description for any other value. */
function needsNote(board: LeaderboardOut): string | undefined {
  return board.min_rounds_applied > 1
    ? `Needs ≥${String(board.min_rounds_applied)} rounds · ${String(board.n_eligible)} qualify`
    : undefined;
}

export function LeaderboardsPage() {
  const meta = useMeta().data;
  const latest = meta?.last_score_date ?? null;
  const pageDefault = usePageDefaultWindow();
  const legacy = useLegacyParams((params) =>
    convertLegacyBoard(params, {
      firstSunday: meta?.first_event_date ?? null,
      lastSunday: latest,
      pageDefault,
    }),
  );
  const { window: timeWindow } = useTimeWindow();
  const [metric, setMetric] = useUrlState<LeaderboardMetric>('metric', METRIC_CODEC, 'avg_score');
  const [asOfParam, setAsOf] = useUrlState<string | null>('as_of', optionalDate, null);
  const [gauge, setGauge] = useUrlState<string | null>('gauge', GAUGE_CODEC, null);
  const [status, setStatus] = useUrlState<ShooterStatus | null>('status', STATUS_CODEC, null);
  const [roundTypes] = useRoundTypes();
  const custom = isCustomWindow(timeWindow);
  // "Board as of" moves a preset's end; a Custom window keeps its own end date.
  const asOf = custom ? null : asOfParam;
  const asked = boardWindow(timeWindow, asOf, latest);
  const board = useLeaderboard({
    period: asked?.period ?? 'season',
    metric,
    asOf: asked?.asOf ?? null,
    gauge,
    status,
    since: asked?.since ?? null,
    enabled: !legacy && asked !== null,
  });
  const data = board.data;
  // An insight link to the board (`lb-board.hl=s:{id}`, metric and period in the page's own keys).
  const { target: boardTarget } = useChartTarget('lb-board');
  useScrollToTarget('lb-board', data !== undefined);

  // While a new query loads, `data` is the previous board: label and format it by what it is, not by the URL.
  const shownMetric = data?.metric ?? metric;
  const chart = useMemo<TabularData>(
    () => ({
      columns: [
        { key: 'display_name', label: 'Shooter', type: 'string' },
        { key: 'value', label: metricLabel(shownMetric), type: 'number' },
      ],
      rows: chartRows((data?.rows ?? []).slice(0, CHART_TOP)),
    }),
    [data, shownMetric],
  );
  // Fullscreen and the CSV: everyone in the standings, not the first ten.
  const full = useMemo<ChartFull | undefined>(() => {
    if (data === undefined) return undefined;
    const rows = chartRows(data.rows);
    return {
      option: barOption(
        { columns: chart.columns, rows },
        { x: 'display_name', y: ['value'], horizontal: true },
      ),
      rows,
      height: Math.max(320, 80 + 28 * rows.length),
      note: 'Everyone in the standings.',
      // The full list covers the same window as the card, so the tag keeps naming it.
      scope: 'windowed',
    };
  }, [data, chart.columns]);
  const ratingIgnoresFilters =
    RATING_METRICS.includes(metric) && (gauge !== null || roundTypes.length > 0);

  let content;
  if (legacy) {
    content = <Skeleton className="h-64" />;
  } else if (board.isError) {
    content = <EmptyState title="Leaderboard unavailable" description="Try again in a moment." />;
  } else if (data === undefined) {
    content = <Skeleton className="h-64" />;
  } else {
    const start = data.start ?? data.event_dates[0] ?? data.end;
    const sundays = data.event_dates.filter((d) => d >= start && d <= data.end).length;
    const where = windowInWords(timeWindow);
    const dates = datesText(start, data.end, latest);
    const tag = custom
      ? dates
      : `${WINDOW_LABELS[timeWindow as keyof typeof WINDOW_LABELS]}${asOf === null ? '' : ` as of ${formatEventDate(data.end)}`} · ${dates}`;
    const note = needsNote(data);
    let body;
    if (data.rows.length === 0) {
      body = (
        <EmptyState
          title={
            sundays === 0 ? `No Sundays with scores in ${where}` : `No one qualifies in ${where}`
          }
          description={sundays === 0 ? undefined : note}
          action={<WidenWindow />}
        />
      );
    } else {
      body = (
        <>
          {note !== undefined && <p className="text-sm text-text-muted">{note}</p>}
          {sundays < THIN_SUNDAYS && (
            <div className="flex flex-col gap-2 rounded-card bg-elevated p-3 text-sm">
              <p>{sundaysNote(sundays, timeWindow)}</p>
              <WidenWindow />
            </div>
          )}
          <ChartFrame
            title={`Top ${String(chart.rows.length)} · ${metricLabel(shownMetric)}`}
            option={barOption(chart, { x: 'display_name', y: ['value'], horizontal: true })}
            columns={chart.columns}
            rows={chart.rows}
            full={full}
            csvName={`leaderboard-${data.metric}-${data.start ?? 'start'}-to-${data.end}`}
            ariaLabel={`${metricLabel(shownMetric)} leaders`}
            urlKey="lb-chart"
            explainer={boardExplainer(shownMetric, data.since === null ? data.period : 'custom')}
          />
          <Card id="chart-lb-board">
            <div className="min-w-0 overflow-x-auto">
              <StandingsTable
                key={`${data.metric}|${data.start ?? ''}|${data.end}`}
                rows={data.rows}
                metric={shownMetric}
                highlight={boardTarget.hl}
              />
            </div>
          </Card>
        </>
      );
    }
    content = (
      <>
        <p className="text-sm font-medium">{tag}</p>
        {body}
      </>
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <h1 className="text-2xl font-medium">Leaderboards</h1>
      <PageTopSlot page="leaderboards" />
      <div role="group" aria-label="Measure" className="hidden flex-wrap gap-2 sm:flex">
        {METRICS.map((m) => (
          <Chip
            key={m.value}
            selected={m.value === metric}
            onClick={() => {
              setMetric(m.value);
            }}
          >
            {m.label}
          </Chip>
        ))}
      </div>
      <label className="flex flex-col gap-1 text-sm sm:hidden">
        Measure
        <select
          value={metric}
          onChange={(event) => {
            setMetric(METRIC_CODEC.parse(event.currentTarget.value));
          }}
          className="min-h-11 rounded-button bg-elevated px-3"
        >
          {METRICS.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </label>
      <div className="flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Gauge
          <select
            value={gauge ?? ''}
            onChange={(event) => {
              setGauge(GAUGE_CODEC.parse(event.currentTarget.value));
            }}
            className="min-h-11 rounded-button bg-elevated px-3"
          >
            <option value="">All gauges</option>
            {GAUGES.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Shooters
          <select
            value={status ?? ''}
            onChange={(event) => {
              setStatus(STATUS_CODEC.parse(event.currentTarget.value));
            }}
            className="min-h-11 rounded-button bg-elevated px-3"
          >
            <option value="">Everyone</option>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!custom && <TimeMachine dates={data?.event_dates ?? []} asOf={asOf} onChange={setAsOf} />}
      {ratingIgnoresFilters && (
        <p role="note" className="text-sm text-text-muted">
          Rating gain ignores the round-type and gauge filters.
        </p>
      )}
      {content}
      {!legacy && <MoversChart asOf={asOf} status={status} />}
    </div>
  );
}
