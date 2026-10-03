import { useMemo } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { Chip } from '../../../components/ui/Chip';
import { useTimeWindow } from '../../../lib/timeWindow';
import { enumCodec, useUrlState } from '../../../lib/useUrlState';
import { useClubMilestones, type MilestoneMetric } from '../api';
import { explainers } from '../explainers';
import { METRIC_CHIPS, totalsModel } from '../milestones';

const METRIC_CODEC = enumCodec(METRIC_CHIPS.map((c) => c.value));

/** Club running totals by Sunday; the query is the section's, shared through the cache. */
export default function TotalsChart() {
  const { data } = useClubMilestones(true);
  const [metric, setMetric] = useUrlState<MilestoneMetric>('mm', METRIC_CODEC, 'clays_thrown');
  const { range } = useTimeWindow();
  const model = useMemo(
    () => (data === undefined ? null : totalsModel(data.series, data.milestones, metric)),
    [data, metric],
  );
  if (model === null) return null;
  return (
    <ChartFrame
      title="Club totals over time"
      option={model.option}
      columns={model.columns}
      rows={model.rows}
      csvName="club-totals"
      ariaLabel="Club running totals by Sunday"
      urlKey="ctot"
      window={range}
      full={{ rows: model.rows, option: model.option, note: 'Every Sunday on record.' }}
      explainer={explainers.ctot}
      controls={
        <div role="group" aria-label="Total" className="flex flex-wrap gap-2">
          {METRIC_CHIPS.map((c) => (
            <Chip key={c.value} selected={c.value === metric} onClick={() => setMetric(c.value)}>
              {c.label}
            </Chip>
          ))}
        </div>
      }
    />
  );
}
