import {
  AGG_LABELS,
  AGGS,
  DIM_LABELS,
  DIMS,
  METRIC_LABELS,
  METRICS,
  type Dim,
  type QuerySpec,
} from '../../../components/charts/explore';
import type { ChartType } from '../../../components/charts/types';
import { Chip } from '../../../components/ui/Chip';
import { Select } from '../../../components/ui/Select';
import { AGGREGATED_METRICS, CHART_TYPES, SORTS, type useExplorerState } from '../urlState';

type Setters = ReturnType<typeof useExplorerState>['set'];

const SORT_LABELS: Record<(typeof SORTS)[number], string> = {
  key_asc: 'Group, ascending',
  key_desc: 'Group, descending',
  value_desc: 'Value, highest first',
  value_asc: 'Value, lowest first',
};
const CHART_LABELS: Record<ChartType, string> = { bar: 'Bar', line: 'Line', heatmap: 'Heatmap' };
const NONE = '' as const;
const dimOptions = [
  { value: NONE, label: 'None' },
  ...DIMS.map((d) => ({ value: d, label: DIM_LABELS[d] })),
];

/** Metric, aggregate, group-by (≤2), sort and chart type. */
export function QueryControls({
  spec,
  chartType,
  set,
}: {
  spec: QuerySpec;
  chartType: ChartType;
  set: Setters;
}) {
  const [first, second] = spec.group_by;
  // Picking the Then by dim as Group by leaves one grouping, never the same dim twice.
  const setDims = (a: Dim | typeof NONE, b: Dim | typeof NONE) =>
    set.dims([...new Set([a, b])].filter((d): d is Dim => d !== NONE));
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1">
      <Select
        label="Metric"
        value={spec.metric}
        options={METRICS.map((m) => ({ value: m, label: METRIC_LABELS[m] }))}
        onChange={set.metric}
      />
      {AGGREGATED_METRICS.includes(spec.metric) && (
        <Select
          label="Aggregate"
          value={spec.agg}
          options={AGGS.map((a) => ({ value: a, label: AGG_LABELS[a] }))}
          onChange={set.agg}
        />
      )}
      <Select
        label="Group by"
        value={first ?? NONE}
        options={dimOptions}
        onChange={(d) => setDims(d, second ?? NONE)}
      />
      <Select
        label="Then by"
        value={second ?? NONE}
        options={dimOptions.filter((o) => o.value === NONE || o.value !== first)}
        onChange={(d) => setDims(first ?? NONE, d)}
      />
      <Select
        label="Sort"
        value={spec.sort}
        options={SORTS.map((s) => ({ value: s, label: SORT_LABELS[s] }))}
        onChange={set.sort}
      />
      <div role="group" aria-label="Chart type" className="flex flex-wrap gap-2">
        {CHART_TYPES.map((t) => (
          <Chip key={t} selected={t === chartType} onClick={() => set.chartType(t)}>
            {CHART_LABELS[t]}
          </Chip>
        ))}
      </div>
    </div>
  );
}
