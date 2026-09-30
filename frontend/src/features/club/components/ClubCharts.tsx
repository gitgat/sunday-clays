import { useMemo } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { useTargetWindow } from '../../../components/charts/chartTarget';
import { useTimeWindow } from '../../../lib/timeWindow';
import { rangeText } from '../../../lib/windowText';
import {
  useClubAttendance,
  useClubCohorts,
  useClubConversion,
  useClubDistribution,
  useClubFirstRounds,
  useClubParity,
  useClubStatusByYear,
  useClubTrends,
} from '../api';
import {
  attendanceModel,
  conversionModel,
  difficultyModel,
  distributionModel,
  firstRoundsModel,
  memberGuestModel,
  newcomersModel,
  parityModel,
  retentionModel,
  scoreTrendModel,
  seasonalityModel,
  yearTrendsModel,
} from '../charts';
import type { ChartModel } from '../charts';
import { explainers } from '../explainers';
import { ChartSlot } from './ChartSlot';
import { useUnfilteredNote } from './roundTypeNote';

export { TurnoutWeatherCard } from './TurnoutWeatherCard';

const NO_DATA = 'No data yet';

/**
 * Every frame on this page has its own urlKey: ChartFrame keeps its Table/Fullscreen state under it (C10).
 * The model is built once per response: a URL change re-renders the round-type-aware charts, and a
 * new option object would redo the model and ChartFrame's zoom for nothing. `build` is a module
 * function and `data` a query result (structurally shared), so both stay stable.
 */
function Frame<T>({
  title,
  subtitle,
  data,
  build,
  name,
  urlKey,
  unfiltered = false,
  windowed = false,
  allYears = false,
}: {
  title: string;
  subtitle: string;
  data: T;
  build: (data: T) => ChartModel;
  name: string;
  urlKey: string;
  /** The endpoint takes no round_type (C8): note that the global filter does not apply. */
  unfiltered?: boolean;
  /** A date-axis time series: the card opens zoomed to the time window; fullscreen shows every Sunday. */
  windowed?: boolean;
  /** Every year, whatever the time window: the subtitle says so. */
  allYears?: boolean;
}) {
  const note = useUnfilteredNote();
  const { range } = useTimeWindow();
  const years = allYears ? ' · all years' : '';
  const model = useMemo(() => build(data), [build, data]);
  return (
    <ChartFrame
      title={title}
      subtitle={`${subtitle}${years}${unfiltered ? note : ''}`}
      explainer={explainers[urlKey]}
      option={model.option}
      window={windowed ? range : null}
      columns={model.columns}
      rows={model.rows}
      csvName={name}
      ariaLabel={`${title} chart`}
      urlKey={urlKey}
    />
  );
}

export function AttendanceChart() {
  const query = useClubAttendance();
  return (
    <ChartSlot
      title="Attendance per Sunday"
      query={query}
      isEmpty={(d) => d.length === 0}
      emptyText="No Sundays yet"
    >
      {(points) => (
        <Frame
          title="Attendance per Sunday"
          subtitle="Head count vs rounds scored each Sunday; shooters with scores in the table"
          data={points}
          build={attendanceModel}
          name="club-attendance"
          urlKey="att"
          unfiltered
          windowed
        />
      )}
    </ChartSlot>
  );
}

export function YearTrendsChart() {
  const query = useClubTrends();
  return (
    <ChartSlot
      title="Shooters and Sundays per year"
      query={query}
      isEmpty={(d) => d.years.length === 0}
      emptyText={NO_DATA}
    >
      {(trends) => (
        <Frame
          title="Shooters and Sundays per year"
          subtitle="Different shooters and Sundays with full results; year-to-date change in the table"
          data={trends.years}
          build={yearTrendsModel}
          name="club-years"
          urlKey="years"
          allYears
          unfiltered
        />
      )}
    </ChartSlot>
  );
}

export function SeasonalityChart() {
  const query = useClubTrends();
  return (
    <ChartSlot
      title="Seasonality"
      query={query}
      isEmpty={(d) => d.months.every((m) => m.n_events === 0)}
      emptyText={NO_DATA}
    >
      {(trends) => (
        <Frame
          title="Seasonality"
          subtitle="Average head count by month of the year (Sundays with full results)"
          data={trends.months}
          build={seasonalityModel}
          name="club-seasonality"
          urlKey="season"
          allYears
          unfiltered
        />
      )}
    </ChartSlot>
  );
}

export function ScoreTrendChart() {
  const query = useClubTrends();
  return (
    <ChartSlot
      title="Median and top score"
      query={query}
      isEmpty={(d) => d.events.length === 0}
      emptyText={NO_DATA}
    >
      {(trends) => (
        <Frame
          title="Median and top score"
          subtitle="Each Sunday with full results, with 8-Sunday averages"
          data={trends.events}
          build={scoreTrendModel}
          name="club-scores"
          urlKey="scores"
          unfiltered
          windowed
        />
      )}
    </ChartSlot>
  );
}

export function DifficultyChart() {
  const query = useClubTrends();
  return (
    <ChartSlot
      title="Difficulty by Sunday"
      query={query}
      isEmpty={(d) => d.events.length === 0}
      emptyText={NO_DATA}
    >
      {(trends) => (
        <Frame
          title="Difficulty by Sunday"
          subtitle="Plus = harder than a typical recent Sunday; 8-Sunday average"
          data={trends.events}
          build={difficultyModel}
          name="club-difficulty"
          urlKey="diff"
          unfiltered
          windowed
        />
      )}
    </ChartSlot>
  );
}

export function DistributionChart() {
  const query = useClubDistribution();
  return (
    <ChartSlot
      title="Score distribution by year"
      query={query}
      isEmpty={(d) => d.length === 0}
      emptyText={NO_DATA}
    >
      {(groups) => (
        <Frame
          title="Score distribution by year"
          subtitle="How common each score was, one hill per year; details in the table"
          data={groups}
          build={distributionModel}
          name="club-distribution"
          urlKey="dist"
          allYears
        />
      )}
    </ChartSlot>
  );
}

export function NewcomersChart() {
  const query = useClubCohorts();
  return (
    <ChartSlot
      title="Newcomers per year"
      query={query}
      isEmpty={(d) => d.length === 0}
      emptyText={NO_DATA}
    >
      {(cohorts) => (
        <Frame
          title="Newcomers per year"
          subtitle="First-time shooters and how many came back (first weeks of records left out)"
          data={cohorts}
          build={newcomersModel}
          name="club-newcomers"
          urlKey="new"
          allYears
          unfiltered
        />
      )}
    </ChartSlot>
  );
}

export function RetentionChart() {
  const query = useClubCohorts();
  return (
    <ChartSlot
      title="Newcomer retention"
      query={query}
      isEmpty={(d) => d.length === 0}
      emptyText={NO_DATA}
    >
      {(cohorts) => (
        <Frame
          title="Newcomer retention"
          subtitle="Share of each year's newcomers who shot again the next year and the year after"
          data={cohorts}
          build={retentionModel}
          name="club-retention"
          urlKey="ret"
          allYears
          unfiltered
        />
      )}
    </ChartSlot>
  );
}

export function MemberGuestChart() {
  const query = useClubStatusByYear();
  return (
    <ChartSlot
      title="Rounds by member status"
      query={query}
      isEmpty={(d) => d.status_by_year.length === 0}
      emptyText={NO_DATA}
    >
      {(summary) => (
        <Frame
          title="Rounds by member status"
          subtitle="Status as recorded on each round"
          data={summary.status_by_year}
          build={memberGuestModel}
          name="club-status"
          urlKey="status"
          allYears
        />
      )}
    </ChartSlot>
  );
}

export function ConversionChart() {
  const query = useClubConversion();
  return (
    <ChartSlot
      title="Guest → member conversion"
      query={query}
      isEmpty={(d) => d.length === 0}
      emptyText={NO_DATA}
    >
      {(years) => (
        <Frame
          title="Guest → member conversion"
          subtitle="Guests first seen each year and how many of them later shot as members"
          data={years}
          build={conversionModel}
          name="club-conversion"
          urlKey="conv"
          allYears
          unfiltered
        />
      )}
    </ChartSlot>
  );
}

export function ParityChart() {
  const query = useClubParity();
  return (
    <ChartSlot
      title="How open is the competition?"
      query={query}
      isEmpty={(d) => d.length === 0}
      emptyText={NO_DATA}
    >
      {(years) => (
        <Frame
          title="How open is the competition?"
          subtitle="Top-3 share of wins and the favorite's win rate; different winners in the table"
          data={years}
          build={parityModel}
          name="club-parity"
          urlKey="parity"
          allYears
          unfiltered
        />
      )}
    </ChartSlot>
  );
}

/** Plan 12 `first-rounds`: an insight link's dates narrow the request (all time otherwise). */
export function FirstRoundsChart() {
  const { range } = useTimeWindow();
  const shown = useTargetWindow('first-rounds', range);
  const query = useClubFirstRounds(shown);
  // An insight link carries its own dates; otherwise the tag names the page's window.
  // The window's own dates are in the tag, so its subtitle says only "the window".
  const span = shown === null || shown === range ? 'the window' : rangeText(shown);
  return (
    <ChartSlot title="First rounds" query={query} isEmpty={(d) => d.n === 0} emptyText={NO_DATA}>
      {(data) => (
        <Frame
          title="First rounds"
          subtitle={`First Sundays in ${span}: each shooter's best round that day`}
          data={data}
          build={firstRoundsModel}
          name="club-first-rounds"
          urlKey="first-rounds"
          unfiltered
        />
      )}
    </ChartSlot>
  );
}
