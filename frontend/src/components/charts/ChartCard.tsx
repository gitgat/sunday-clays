import type { ECElementEvent } from 'echarts';
import { useMemo } from 'react';
import { useNavigate } from 'react-router';
import { api, unwrap } from '../../api/client';
import { formatNumber } from '../../lib/format';
import { ROUND_TYPE_LABELS, useRoundTypeHref, useRoundTypes } from '../../lib/roundTypes';
import { boolCodec, enumCodec, useUrlState } from '../../lib/useUrlState';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Chip } from '../ui/Chip';
import { EmptyState } from '../ui/EmptyState';
import { Skeleton } from '../ui/Skeleton';
import { ChartFrame } from './ChartFrame';
import type { EChartEvents } from './EChart';
import {
  DIM_LABELS,
  METRIC_LABELS,
  bestRoundApplies,
  buildExploreOption,
  rowForClick,
  toTabular,
  useExplore,
  type Dim,
  type Filters,
  type Metric,
  type QuerySpec,
} from './explore';
import type { ChartFullQuery, ChartType, Explainer, TabularRow } from './types';

export interface ChartCardProps {
  title: string;
  subtitle?: string | undefined;
  spec: QuerySpec;
  /** Offered chart types; the first is the default. */
  chartTypes: ChartType[];
  /** Choices for the first group-by dim (chips); default: fixed to spec.group_by[0]. */
  allowedGroupBy?: Dim[] | undefined;
  /** Metric choices (chips); default: fixed to spec.metric. */
  allowedMetrics?: Metric[] | undefined;
  urlKey: string;
  /** href for a clicked bar/point/cell or table row; the global `rt` filter is added. */
  drill?: ((row: TabularRow) => string) | undefined;
  /** Plain-language "About this chart" copy, passed to the ChartFrame. */
  explainer?: Explainer | undefined;
  /** The spec's dates were filled from the time window, so the date chips are left out. */
  datesFromWindow?: boolean;
  /**
   * The query fullscreen and the CSV run instead of `spec`, e.g. `allHistorySpec` (every row, all
   * dates). Fetched only when fullscreen opens or CSV is pressed. Default: the card's own rows.
   */
  fullSpec?: ((spec: QuerySpec) => QuerySpec) | undefined;
}

const CHART_TYPE_LABELS: Record<ChartType, string> = {
  bar: 'Bar',
  line: 'Line',
  heatmap: 'Heatmap',
};

/** Read-only chips describing the card's own filters (the global round type has its own chip). */
function filterLabels(
  filters: Filters,
  cardRoundTypes: boolean,
  datesFromWindow: boolean,
): string[] {
  const labels: string[] = [];
  if (cardRoundTypes) {
    labels.push(`Round type: ${filters.round_types.map((t) => ROUND_TYPE_LABELS[t]).join(' + ')}`);
  }
  // The time window names its own dates in the tag beside the title; repeating them is noise.
  if (filters.date_from && !datesFromWindow) labels.push(`From ${filters.date_from}`);
  if (filters.date_to && !datesFromWindow) labels.push(`To ${filters.date_to}`);
  if (filters.statuses.length) labels.push(`Status: ${filters.statuses.join(', ')}`);
  if (filters.gauges.length) labels.push(`Gauge: ${filters.gauges.join(', ')}`);
  if (filters.shooter_ids.length) labels.push(`${filters.shooter_ids.length} shooter(s)`);
  if (filters.min_rounds > 0) labels.push(`≥${filters.min_rounds} rounds`);
  if (filters.temp_f) labels.push(`${filters.temp_f[0]}–${filters.temp_f[1]} °F`);
  if (filters.gust_mph) labels.push(`Gusts ${filters.gust_mph[0]}–${filters.gust_mph[1]} mph`);
  if (filters.precip_in) labels.push(`Rain ${filters.precip_in[0]}–${filters.precip_in[1]} in`);
  return labels;
}

/** ChartFrame + explore controls over POST /api/explore (C10). All control state lives in the URL. */
export function ChartCard({
  title,
  subtitle,
  spec,
  chartTypes,
  allowedGroupBy,
  allowedMetrics,
  urlKey,
  drill,
  explainer,
  datesFromWindow = false,
  fullSpec,
}: ChartCardProps) {
  const navigate = useNavigate();
  const drillHref = useRoundTypeHref();
  const [globalRoundTypes] = useRoundTypes();
  const metrics = allowedMetrics ?? [spec.metric];
  const dims = allowedGroupBy ?? (spec.group_by[0] === undefined ? [] : [spec.group_by[0]]);
  const [metric, setMetric] = useUrlState(`${urlKey}.m`, enumCodec(metrics), spec.metric);
  const [primary, setPrimary] = useUrlState<Dim | ''>(
    `${urlKey}.g`,
    enumCodec<Dim | ''>(dims),
    spec.group_by[0] ?? '',
  );
  const [chartType, setChartType] = useUrlState(
    `${urlKey}.t`,
    enumCodec(chartTypes),
    chartTypes[0] ?? 'bar',
  );
  const [bestOnly, setBestOnly] = useUrlState(
    `${urlKey}.b`,
    boolCodec,
    spec.filters.best_round_only,
  );

  // The engine rejects best_round_only for some metrics (attendance): no chip, and a flag left
  // in the URL from another metric is not sent.
  const bestApplies = bestRoundApplies(metric);
  const cardRoundTypes = spec.filters.round_types.length > 0;
  const effective = useMemo<QuerySpec>(
    () => ({
      ...spec,
      metric,
      group_by: [
        ...new Set([primary, ...spec.group_by.slice(1)].filter((d): d is Dim => d !== '')),
      ],
      filters: {
        ...spec.filters,
        best_round_only: bestApplies && bestOnly,
        round_types: cardRoundTypes ? spec.filters.round_types : globalRoundTypes,
      },
    }),
    [spec, metric, primary, bestApplies, bestOnly, cardRoundTypes, globalRoundTypes],
  );
  const query = useExplore(effective);

  const controls = (
    <>
      {metrics.length > 1 &&
        metrics.map((m) => (
          <Chip key={m} selected={m === metric} onClick={() => setMetric(m)}>
            {METRIC_LABELS[m]}
          </Chip>
        ))}
      {dims.length > 1 &&
        dims.map((d) => (
          <Chip key={d} selected={d === primary} onClick={() => setPrimary(d)}>
            By {DIM_LABELS[d].toLowerCase()}
          </Chip>
        ))}
      {chartTypes.length > 1 &&
        chartTypes.map((t) => (
          <Chip key={t} selected={t === chartType} onClick={() => setChartType(t)}>
            {CHART_TYPE_LABELS[t]}
          </Chip>
        ))}
      {bestApplies && (
        <Chip selected={bestOnly} onClick={() => setBestOnly(!bestOnly)}>
          Best round only
        </Chip>
      )}
      {filterLabels(effective.filters, cardRoundTypes, datesFromWindow).map((label) => (
        <Chip key={label}>{label}</Chip>
      ))}
    </>
  );

  // Built once per result on screen (and chart type): the card re-renders on every URL change,
  // and a new option object would defeat ChartFrame's memoized zoom and redo this work.
  // Render with the spec that produced the data: while a new spec loads the previous one stays.
  const shown = useMemo(() => {
    if (query.data === undefined || query.data.result.rows.length === 0) return null;
    const data = toTabular(query.data.result);
    const groupBy = query.data.spec.group_by;
    return { data, groupBy, option: buildExploreOption(data, groupBy, chartType) };
  }, [query.data, chartType]);

  // Its own key ('chart-full'): ['/api/explore', spec] holds an ExploreData, not a ChartFull.
  const fullQuery = useMemo<ChartFullQuery | undefined>(() => {
    if (fullSpec === undefined) return undefined;
    const full = fullSpec(effective);
    return {
      queryKey: ['/api/explore', full, 'chart-full', chartType],
      queryFn: async () => {
        const result = await unwrap(api.POST('/api/explore', { body: full }));
        const tabular = toTabular(result);
        return {
          option: buildExploreOption(tabular, full.group_by, chartType),
          columns: tabular.columns,
          rows: tabular.rows,
          note: result.truncated
            ? `Showing the first ${formatNumber(tabular.rows.length)} rows`
            : undefined,
        };
      },
    };
  }, [fullSpec, effective, chartType]);

  if (query.isPending) {
    return (
      <Card title={title} subtitle={subtitle}>
        <Skeleton label={`Loading ${title}`} lines={6} />
      </Card>
    );
  }
  if (query.isError) {
    // Keep the chips: "Try again" repeats the same spec, so a choice the server rejects
    // (invalid_query) is undone by picking another chip.
    return (
      <Card title={title} subtitle={subtitle}>
        <div className="mb-3 flex flex-wrap gap-2">{controls}</div>
        <EmptyState
          title="Couldn't load this chart"
          description={query.error.message}
          action={<Button onClick={() => void query.refetch()}>Try again</Button>}
        />
      </Card>
    );
  }

  if (shown === null) {
    return (
      <Card title={title} subtitle={subtitle}>
        <div className="mb-3 flex flex-wrap gap-2">{controls}</div>
        <EmptyState
          title="No data for these filters"
          description="Try a wider date range or fewer filters."
        />
      </Card>
    );
  }

  // Match the click against the grouping of the chart on screen, never the one still loading.
  const { data, groupBy: shownGroupBy, option } = shown;
  const onEvents: EChartEvents | undefined = drill && {
    click: (params: ECElementEvent) => {
      const row = rowForClick(
        data,
        shownGroupBy,
        params as { name?: string; seriesName?: string; seriesType?: string; value?: unknown },
      );
      if (row) void navigate(drillHref(drill(row)));
    },
  };
  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      option={option}
      columns={data.columns}
      rows={data.rows}
      csvName={urlKey}
      ariaLabel={title}
      urlKey={`${urlKey}.v`}
      controls={
        <>
          {controls}
          {query.data.result.truncated && (
            // The server stopped at spec.limit: say so rather than show a partial set as complete.
            <p className="basis-full text-sm text-text-muted">
              Showing the first {formatNumber(data.rows.length)} rows
            </p>
          )}
        </>
      }
      onEvents={onEvents}
      rowHref={drill}
      explainer={explainer}
      fullQuery={fullQuery}
    />
  );
}
