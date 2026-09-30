import { useMemo } from 'react';
import { ChartCard } from '../../../components/charts/ChartCard';
import { allHistorySpec, querySpec } from '../../../components/charts/explore';
import { useSettledWindow } from '../../../components/charts/useSettledWindow';
import { ThinWindowNudge } from '../../../components/ThinWindowNudge';
import { Card } from '../../../components/ui/Card';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useWindowEvents } from '../../../lib/windowEvents';
import { explainers } from '../explainers';

const TITLE = 'Turnout vs weather';

/**
 * Average head count per weather condition or band, through the Explorer (C9 metric `attendance`),
 * for the Sundays inside the time window. `querySpec` fills the server-defaulted fields the
 * generated QuerySpec type marks required.
 */
export function TurnoutWeatherCard() {
  const { settled, range } = useSettledWindow();
  const { sundays, isPending, error: sundaysError } = useWindowEvents();
  const spec = useMemo(
    () =>
      querySpec({
        metric: 'attendance',
        agg: 'avg',
        group_by: ['condition'],
        filters: { date_from: range?.from ?? null, date_to: range?.to ?? null },
      }),
    [range],
  );
  // Wait for the window's anchor so the card runs one query, not an unfiltered one and then this.
  if (!settled) {
    return (
      <Card title={TITLE}>
        <Skeleton label={`Loading ${TITLE}`} lines={6} />
      </Card>
    );
  }
  return (
    <div className="flex min-w-0 flex-col gap-2">
      {!isPending && sundaysError === null && <ThinWindowNudge sundays={sundays} />}
      <ChartCard
        title={TITLE}
        subtitle="Average head count by weather condition or band"
        spec={spec}
        chartTypes={['bar']}
        allowedGroupBy={['condition', 'temp_band', 'wind_band', 'precip_band']}
        allowedMetrics={['attendance']}
        urlKey="turnout"
        datesFromWindow={range !== null}
        fullSpec={allHistorySpec}
        explainer={explainers.turnout}
      />
    </div>
  );
}
