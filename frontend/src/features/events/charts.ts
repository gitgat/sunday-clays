import type { EChartsOption } from 'echarts';
import { colors } from '../../theme/tokens';
import { heatmapOption } from '../../components/charts/builders/heatmap';
import type { TabularData } from '../../components/charts/types';
import type { EventResult, StationMatrix } from './api';

export type ChartModel = TabularData & { option: EChartsOption };

type Entry = StationMatrix['entries'][number];

/**
 * Pairs each entry with a display label: the matched shooter's name, else the sheet's name key (an unmatched
 * station name, C5). A repeated label gets " (2)", " (3)" so heatmap rows never collide.
 */
function labelled(entries: Entry[]): { entry: Entry; label: string }[] {
  const seen = new Map<string, number>();
  return entries.map((entry) => {
    const name = entry.display_name ?? entry.name_key;
    const n = (seen.get(name) ?? 0) + 1;
    seen.set(name, n);
    return { entry, label: n === 1 ? name : `${name} (${n})` };
  });
}

function hitsAt(entry: Entry, label: string): number | null {
  return entry.hits.find((cell) => cell.label === label)?.hits ?? null;
}

type Layout = StationMatrix['layout'][number];

/** A station thrown out carries a `*` in its heatmap name. */
function stationName(s: Layout): string {
  return s.dropped ? `Stn ${s.label} *` : `Stn ${s.label}`;
}

export function stationLongData(matrix: StationMatrix): TabularData {
  return {
    columns: [
      { key: 'shooter', label: 'Shooter', type: 'string' },
      { key: 'station', label: 'Station', type: 'string' },
      { key: 'hits', label: 'Hits', type: 'int' },
    ],
    rows: labelled(matrix.entries).flatMap(({ entry, label }) =>
      matrix.layout.map((s) => ({
        shooter: label,
        station: stationName(s),
        hits: s.dropped ? null : hitsAt(entry, s.label),
      })),
    ),
  };
}

/** Station table + heatmap; `results` supply the recorded score of the round each entry is linked to. */
export function stationMatrixModel(
  matrix: StationMatrix,
  results: readonly Pick<EventResult, 'round_id' | 'score'>[],
): ChartModel {
  const columns: TabularData['columns'] = [
    { key: 'shooter', label: 'Shooter', type: 'string' },
    ...matrix.layout.map((s) => ({
      key: `s${s.label}`,
      label: s.dropped
        ? `Stn ${s.label} * (${s.target_count})`
        : `Stn ${s.label} (${s.target_count})`,
      type: s.dropped ? ('string' as const) : ('int' as const),
    })),
    { key: 'total', label: 'Station total', type: 'int' },
    { key: 'score', label: 'Score', type: 'int' },
  ];
  const rows = labelled(matrix.entries).map(({ entry, label }) => {
    const row: TabularData['rows'][number] = { shooter: label };
    for (const s of matrix.layout)
      row[`s${s.label}`] = s.dropped ? 'credited' : hitsAt(entry, s.label);
    row.total = entry.total;
    row.score =
      results.find((r) => entry.round_id !== null && r.round_id === entry.round_id)?.score ?? null;
    return row;
  });
  const option = heatmapOption(stationLongData(matrix), {
    x: 'station',
    y: 'shooter',
    value: 'hits',
  });
  const dropped = matrix.layout.filter((s) => s.dropped).map(stationName);
  if (dropped.length > 0 && Array.isArray(option.series)) {
    // The thrown-out columns have no hits to colour: grey them instead of reading as zero.
    option.series = option.series.map((series, i) =>
      i === 0
        ? {
            ...series,
            markArea: {
              silent: true,
              itemStyle: { color: colors.outlineVariant },
              data: dropped.map((l) => [{ xAxis: l }, { xAxis: l }]),
            },
          }
        : series,
    ) as typeof option.series;
  }
  return { columns, rows, option };
}
