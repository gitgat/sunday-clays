import type { EChartsOption } from 'echarts';
import { useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { barOption } from '../../../components/charts/builders/bar';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery, Explainer, TabularData } from '../../../components/charts/types';
import { api, unwrap } from '../../../api/client';
import { useRoundTypes } from '../../../lib/roundTypes';
import type { WindowRange } from '../../../lib/timeWindow';
import type { EventSummary } from '../api';
import { homeExplainers } from '../explainers';
import { turnout } from '../turnout';

const FRESH_MS = 60_000;

export function turnoutModel(events: EventSummary[]): TabularData & { option: EChartsOption } {
  const columns: TabularData['columns'] = [
    { key: 'event_date', label: 'Date', type: 'date' },
    { key: 'shooters', label: 'People', type: 'int' },
  ];
  const rows = events
    .filter((e) => e.has_scores)
    .sort((a, b) => a.event_date.localeCompare(b.event_date))
    .map((e) => ({ event_date: e.event_date, shooters: turnout(e) }));
  return {
    columns,
    rows,
    // ChartFrame opens the card on the time window; fullscreen shows every Sunday.
    option: barOption({ columns, rows }, { x: 'event_date', y: ['shooters'] }),
  };
}

/**
 * Turnout per Sunday. ClubPulse loads this module lazily: it pulls in ChartFrame and ECharts, and
 * the home page's text cards must not wait for them.
 */
export function TurnoutChart({
  events,
  range,
  label,
  explainer = homeExplainers.pulse,
}: {
  events: EventSummary[];
  range: WindowRange;
  /** The window's name, for the accessible label. */
  label: string;
  /** The Sunday Sheet's fixed 8 weeks explain themselves differently (Plan 14). */
  explainer?: Explainer;
}) {
  const [roundTypes] = useRoundTypes();
  const queryClient = useQueryClient();
  const model = useMemo(() => turnoutModel(events), [events]);
  // Fullscreen and the CSV: every scored Sunday on record, in one request (no year, no window).
  const fullQuery = useMemo<ChartFullQuery>(
    () => ({
      queryKey: ['/api/events', 'all', roundTypes, 'chart-full'],
      queryFn: async () => {
        const all = await queryClient.fetchQuery({
          queryKey: ['/api/events', { from: null, to: null, round_type: roundTypes }],
          queryFn: () =>
            unwrap(api.GET('/api/events', { params: { query: { round_type: roundTypes } } })),
          staleTime: FRESH_MS,
        });
        return { ...turnoutModel(all), note: 'Every Sunday with scores on record.' };
      },
    }),
    [queryClient, roundTypes],
  );
  return (
    <ChartFrame
      title="Turnout per Sunday"
      subtitle="Head count each Sunday"
      option={model.option}
      window={range}
      emptyWindow={{ none: 'No scored Sundays', last: 'Latest scored Sunday' }}
      fullQuery={fullQuery}
      columns={model.columns}
      rows={model.rows}
      csvName={`turnout-${range.to}`}
      ariaLabel={`Turnout per Sunday, ${label.toLowerCase()}`}
      urlKey="pulse"
      explainer={explainer}
    />
  );
}
