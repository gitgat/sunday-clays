import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { EventResult, StationMatrix } from '../api';
import { stationMatrixModel } from '../charts';
import { eventExplainers } from '../explainers';
import { formatDay } from '../format';

/** 20 px per sheet entry plus axes and the colour scale, so every shooter label stays legible. */
function chartHeight(entries: number): number {
  return Math.max(320, 120 + 20 * entries);
}

/** Only rendered for an event with a station sheet (the page lazy-loads it: it pulls in ECharts). */
export function StationHeatmap({
  stations,
  results,
  date,
}: {
  stations: StationMatrix;
  results: EventResult[];
  date: string;
}) {
  const model = stationMatrixModel(stations, results);
  return (
    <ChartFrame
      title="Station hits"
      subtitle="Hits per shooter at each station"
      option={model.option}
      columns={model.columns}
      rows={model.rows}
      csvName={`stations-${date}`}
      ariaLabel={`Station hits heatmap for ${formatDay(date)}`}
      urlKey="stn"
      zoom="none"
      explainer={eventExplainers.stn}
      height={chartHeight(stations.entries.length)}
    />
  );
}
