import { useId, useMemo, useState } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { shooterLabels } from '../../../components/charts/chartTarget';
import {
  DIM_LABELS,
  allHistorySpec,
  buildExploreOption,
  toTabular,
  EVENT_METRICS,
  useExplore,
  withCompare,
  type QueryResult,
  type QuerySpec,
} from '../../../components/charts/explore';
import { api, unwrap } from '../../../api/client';
import type { ChartFull, ChartType, Explainer, TabularRow } from '../../../components/charts/types';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { Chip } from '../../../components/ui/Chip';
import { EmptyState } from '../../../components/ui/EmptyState';
import { ExplainerPanel, ExplainerToggle } from '../../../components/ui/Explainer';
import { Skeleton } from '../../../components/ui/Skeleton';
import { ThinWindowNudge } from '../../../components/ThinWindowNudge';
import { formatNumber } from '../../../lib/format';
import { useWindowEvents } from '../../../lib/windowEvents';
import { CHOICES_EXPLAINER, explorerExplainer } from '../explainers';
import { FilterControls, activeFilterCount } from '../components/FilterControls';
import { QueryControls } from '../components/QueryControls';
import { useExplorerState } from '../urlState';

/** The compare line's name: insight links compare one shooter with everyone (Plan 12). */
const COMPARE_NAME = 'Everyone';

function describe(spec: QuerySpec, valueLabel: string): string {
  // "Sunday" is a proper noun in the app's copy: it keeps its capital.
  const dims = spec.group_by.map((d) =>
    d === 'event' ? DIM_LABELS[d] : DIM_LABELS[d].toLowerCase(),
  );
  return dims.length ? `${valueLabel} by ${dims.join(' and ')}` : valueLabel;
}

interface RowLink {
  href: (row: TabularRow) => string;
  /** The table column that carries the link: the dim's own cell, never a later text column. */
  key: string;
}

/** Links a result row to the page for its first dim (shooter profile or event), if any. */
function rowLink(spec: QuerySpec): RowLink | undefined {
  const first = spec.group_by[0];
  if (first === 'shooter') {
    return { key: 'shooter', href: (row) => `/shooters/${String(row.shooter_id)}` };
  }
  if (first === 'event') return { key: 'event', href: (row) => `/events/${String(row.event)}` };
  return undefined;
}

/** The "About these choices" disclosure under the Query controls. */
function ChoicesHelp() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div className="mt-2">
      <ExplainerToggle
        label="About these choices"
        panelId={panelId}
        open={open}
        onToggle={() => setOpen((v) => !v)}
      />
      {open && <ExplainerPanel id={panelId} explainer={CHOICES_EXPLAINER} />}
    </div>
  );
}

/** The chart for one result (and the optional compare line): the card and fullscreen share it. */
function exploreOption(
  tabular: ReturnType<typeof toTabular>,
  data: QueryResult,
  groupBy: QuerySpec['group_by'],
  chartType: ChartType,
  compare?: QueryResult,
) {
  const base = data.rows.length === 0 ? null : buildExploreOption(tabular, groupBy, chartType);
  return base === null || compare === undefined
    ? base
    : withCompare(base, toTabular(compare), groupBy, COMPARE_NAME);
}

export function ExplorerPage() {
  const state = useExplorerState();
  // The query's dates are always the header's time window (the URL's old From/To become a Custom
  // window). Wait for the window's anchor so the page runs one query, not two.
  const { settled, range } = state;
  const effective = state.spec;
  const query = useExplore(effective, { enabled: settled });
  const { sundays, isPending: sundaysPending, error: sundaysError } = useWindowEvents();
  // The compare line (Plan 12 `cmp.*`) covers the same dates as the main query.
  const compareSpec = useMemo<QuerySpec | null>(
    () =>
      state.compare === null
        ? null
        : {
            ...state.compare,
            filters: {
              ...state.compare.filters,
              date_from: effective.filters.date_from,
              date_to: effective.filters.date_to,
            },
          },
    [state.compare, effective],
  );
  const compared = useExplore(compareSpec ?? effective, {
    enabled: settled && compareSpec !== null,
  });
  const filters = activeFilterCount(state.spec);
  const byTime = state.spec.group_by.some((d) => d === 'event' || d === 'month');
  // Open at first when the URL carries filters; afterwards only the user opens or closes it, so
  // clearing the last filter never collapses the panel mid-edit.
  const [filtersOpen, setFiltersOpen] = useState(filters > 0);
  // Built once per result on screen (and chart type): the page re-renders on every URL change
  // and panel toggle, and a new option object would defeat ChartFrame's memoized zoom. Drawn
  // with the spec that produced the data, never a newer one still loading (D18).
  const { chartType } = state;
  const compareData = state.compare === null ? undefined : compared.data;
  const shown = useMemo(() => {
    if (query.data === undefined) return null;
    const { spec, result: data } = query.data;
    const tabular = toTabular(data);
    const option = exploreOption(tabular, data, spec.group_by, chartType, compareData?.result);
    return { spec, data, tabular, option };
  }, [query.data, compareData, chartType]);
  // Fullscreen and the CSV: every row the engine allows, over every date. Built from the spec that
  // produced the result on screen (like the card), never a newer one still loading. The compare
  // line follows the same dates and limit.
  const shownSpec = shown?.spec ?? effective;
  // A window that already reaches back to the first Sunday has nothing more to say.
  const lifted = shownSpec.filters.date_from !== null;
  const fullSpec = useMemo(() => allHistorySpec(shownSpec), [shownSpec]);
  const fullCompareSpec = useMemo<QuerySpec | null>(
    () =>
      state.compare === null
        ? null
        : {
            ...state.compare,
            limit: fullSpec.limit,
            filters: {
              ...state.compare.filters,
              date_from: fullSpec.filters.date_from,
              date_to: fullSpec.filters.date_to,
            },
          },
    [state.compare, fullSpec],
  );
  const fullQuery = useMemo(
    () => ({
      queryKey: ['/api/explore', fullSpec, fullCompareSpec, 'chart-full', chartType],
      queryFn: async (): Promise<ChartFull> => {
        const [data, compareResult] = await Promise.all([
          unwrap(api.POST('/api/explore', { body: fullSpec })),
          fullCompareSpec === null
            ? Promise.resolve(null)
            : unwrap(api.POST('/api/explore', { body: fullCompareSpec })),
        ]);
        const tabular = toTabular(data);
        const option = exploreOption(
          tabular,
          data,
          fullSpec.group_by,
          chartType,
          compareResult ?? undefined,
        );
        const cut = data.truncated
          ? `Showing the first ${formatNumber(data.rows.length)} rows.`
          : '';
        const note = [lifted ? 'Every Sunday on record, not just the time window.' : '', cut]
          .filter((part) => part !== '')
          .join(' ');
        return {
          columns: tabular.columns,
          rows: tabular.rows,
          ...(option === null ? {} : { option }),
          ...(note === '' ? {} : { note }),
        };
      },
    }),
    [fullSpec, fullCompareSpec, chartType, lifted],
  );

  let result;
  if (query.isError) {
    result = (
      <Card title="Result">
        <EmptyState
          title="This query can't run"
          description={query.error.message}
          action={<Button onClick={() => void query.refetch()}>Try again</Button>}
        />
      </Card>
    );
  } else if (shown === null) {
    result = (
      <Card title="Result">
        <Skeleton label="Running query" lines={8} />
      </Card>
    );
  } else {
    const { spec, data, tabular, option } = shown;
    const link = rowLink(spec);
    const valueLabel = data.columns.find((c) => c.key === 'value')?.label ?? 'Value';
    // The numbers on screen cover the time window (all history when nothing is scored yet). The
    // spec that produced them may be a step behind the URL, and then it names no window.
    const sent = spec.filters;
    const current = range === null || (sent.date_from === range.from && sent.date_to === range.to);
    const scope: Explainer['scope'] = !current
      ? undefined
      : range === null
        ? 'all-time'
        : 'windowed';
    const subtitle = [
      // Attendance is a per-Sunday head count; the engine has no round count for it.
      EVENT_METRICS.has(spec.metric) ? null : `Based on ${formatNumber(data.n_rounds)} rounds`,
      data.truncated ? `showing the first ${formatNumber(data.rows.length)} rows` : null,
    ]
      .filter((part) => part !== null)
      .join(' · ');
    const title = describe(spec, valueLabel);
    result =
      option === null ? (
        <Card title={title}>
          <EmptyState
            title="No data for these filters"
            description="Try a wider date range or fewer filters. The time window in the top bar also limits the dates."
          />
        </Card>
      ) : (
        <ChartFrame
          title={title}
          subtitle={subtitle === '' ? undefined : subtitle}
          option={option}
          columns={tabular.columns}
          rows={tabular.rows}
          csvName={`explorer-${spec.metric}${spec.group_by.length ? `-by-${spec.group_by.join('-')}` : ''}`}
          ariaLabel={title}
          urlKey="v"
          fullQuery={fullQuery}
          height={420}
          rowHref={link?.href}
          rowHrefKey={link?.key}
          explainer={explorerExplainer(spec.metric, scope)}
          hlLabels={spec.group_by[0] === 'shooter' ? shooterLabels('shooter') : undefined}
          controls={
            state.compare === null || compareData === undefined ? undefined : (
              <Chip onRemove={state.set.clearCompare} removeLabel="Stop comparing">
                {`Dashed line: ${COMPARE_NAME.toLowerCase()}`}
              </Chip>
            )
          }
        />
      );
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-text">Explorer</h1>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card title="Query">
            <QueryControls spec={state.spec} chartType={state.chartType} set={state.set} />
            <ChoicesHelp />
          </Card>
          <Card>
            <details open={filtersOpen} onToggle={(e) => setFiltersOpen(e.currentTarget.open)}>
              <summary className="min-h-11 cursor-pointer py-2 text-base font-medium text-text">
                Filters{filters > 0 ? ` (${filters})` : ''}
              </summary>
              <div className="pt-3">
                <FilterControls spec={state.spec} ranges={state.ranges} set={state.set} />
              </div>
            </details>
          </Card>
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          {/* A split by Sunday or month is fine on a short window; any other split needs more Sundays. */}
          {!sundaysPending && sundaysError === null && !byTime && (
            <ThinWindowNudge
              sundays={sundays}
              need="Comparing groups needs more; try a longer window."
            />
          )}
          {result}
        </div>
      </div>
    </div>
  );
}
