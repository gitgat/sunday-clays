import { useMemo } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { ThinWindowNudge } from '../../../components/ThinWindowNudge';
import type { ChartFull } from '../../../components/charts/types';
import { useRoundTypes } from '../../../lib/roundTypes';
import {
  filterRowsByWindow,
  useMeta,
  useTimeWindow,
  type WindowRange,
} from '../../../lib/timeWindow';
import { enumCodec, useUrlState } from '../../../lib/useUrlState';
import {
  fetchAllWeatherEffects,
  fetchAllWeatherTurnout,
  useWeatherEffects,
  useWeatherEvents,
  useWeatherSensitivity,
  useWeatherTurnout,
  type WeatherEvent,
} from '../api';
import {
  bandScoreChart,
  difficultyFitChart,
  sensitivityChart,
  turnoutChart,
  windRoseChart,
  type ChartModel,
} from '../charts';
import { ConditionsExplorer } from '../components/ConditionsExplorer';
import { explainers } from '../explainers';
import {
  COVARIATE_LABELS,
  DIMENSIONS,
  DIMENSION_LABELS,
  MODEL_COVARIATES,
  SENSITIVITY_COVARIATES,
  type Dimension,
  type ModelCovariate,
  type SensitivityCovariate,
} from '../format';

const covariateCodec = enumCodec(MODEL_COVARIATES);
const dimensionCodec = enumCodec(DIMENSIONS);
const sensitivityCodec = enumCodec(SENSITIVITY_COVARIATES);

/** A chart model's option and table, with the note for fullscreen. */
const toFull = (m: ChartModel, note: string): ChartFull => ({
  option: m.option,
  columns: m.data.columns,
  rows: m.data.rows,
  note,
});

function Pending({ isError, what }: { isError: boolean; what: string }) {
  return isError ? (
    <p role="alert">Could not load {what}.</p>
  ) : (
    <p role="status">Loading {what}…</p>
  );
}

function Picker<T extends string>({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly T[];
  labels: Record<T, string>;
  onChange: (next: T) => void;
}) {
  return (
    <label className="flex min-w-0 items-center gap-2">
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="min-h-11 min-w-0 max-w-full rounded-button bg-surface px-3"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {labels[o]}
          </option>
        ))}
      </select>
    </label>
  );
}

const EVERY_SUNDAY = 'Every Sunday with weather.';
const EVERY_SUNDAY_ON_RECORD = 'Every Sunday with weather on record.';

const SENSITIVITY_LABELS: Record<SensitivityCovariate, string> = {
  temp_f: 'Temperature, per 10 °F',
  gust_mph: 'Gusts, per 10 mph',
  precip_in: 'Rain, per 0.1 in',
};

const SENSITIVITY_NOUNS: Record<SensitivityCovariate, string> = {
  temp_f: 'temperature',
  gust_mph: 'wind gusts',
  precip_in: 'rain',
};

function WeatherCharts({ events, range }: { events: WeatherEvent[]; range: WindowRange }) {
  const [roundTypes] = useRoundTypes();
  const effects = useWeatherEffects(range);
  const sensitivity = useWeatherSensitivity();
  const turnout = useWeatherTurnout(range);
  const [covariate, setCovariate] = useUrlState<ModelCovariate>('wx', covariateCodec, 'gust_mph');
  const [dimension, setDimension] = useUrlState<Dimension>('wdim', dimensionCodec, 'temp_band');
  const [sensitivityCovariate, setSensitivityCovariate] = useUrlState<SensitivityCovariate>(
    'wsc',
    sensitivityCodec,
    'gust_mph',
  );
  // The round-type filter, applied once: the card also windows it, fullscreen and the CSV do not.
  const allShown = useMemo(
    () =>
      roundTypes.length === 0
        ? events
        : events.filter((e) => roundTypes.some((rt) => rt === e.round_type)),
    [events, roundTypes],
  );
  const shown = useMemo(() => filterRowsByWindow(allShown, 'event_date', range), [allShown, range]);
  const fit = difficultyFitChart(shown, effects.data?.model ?? null, covariate);
  const rose = windRoseChart(shown);
  const sensitivityModel = sensitivity.data
    ? sensitivityChart(sensitivity.data.shooters, sensitivityCovariate, sensitivity.data.tau2)
    : null;
  const model = effects.data?.model ?? null;
  const fitFull = useMemo<ChartFull>(() => {
    const all = difficultyFitChart(allShown, model, covariate);
    return toFull(all, EVERY_SUNDAY);
  }, [allShown, model, covariate]);
  const roseFull = useMemo<ChartFull>(() => {
    const all = windRoseChart(allShown);
    return toFull(all, EVERY_SUNDAY);
  }, [allShown]);
  const bandFullQuery = useMemo(
    () => ({
      queryKey: ['/api/weather/effects', roundTypes, 'all', 'chart-full', dimension],
      queryFn: async (): Promise<ChartFull> => {
        const all = bandScoreChart((await fetchAllWeatherEffects(roundTypes)).bands, dimension);
        return toFull(all, EVERY_SUNDAY_ON_RECORD);
      },
    }),
    [roundTypes, dimension],
  );
  const turnoutFullQuery = useMemo(
    () => ({
      queryKey: ['/api/weather/turnout', 'all', 'chart-full', dimension],
      queryFn: async (): Promise<ChartFull> => {
        const all = turnoutChart(await fetchAllWeatherTurnout(), dimension);
        return toFull(all, EVERY_SUNDAY_ON_RECORD);
      },
    }),
    [dimension],
  );
  const sensitivityShooters = sensitivity.data?.shooters;
  const sensitivityTau2 = sensitivity.data?.tau2;
  const sensitivityFull = useMemo<ChartFull | undefined>(() => {
    if (sensitivityShooters === undefined) return undefined;
    const all = sensitivityChart(
      sensitivityShooters,
      sensitivityCovariate,
      sensitivityTau2,
      Infinity,
    );
    // A flat measure draws nothing, so it keeps the inline (empty) chart.
    if (all.flat) return undefined;
    const bars = all.data.rows.length;
    return { option: all.option, height: Math.max(320, 64 + 24 * bars) };
  }, [sensitivityShooters, sensitivityTau2, sensitivityCovariate]);
  const dimensionPicker = (label: string) => (
    <Picker
      label={label}
      value={dimension}
      options={DIMENSIONS}
      labels={DIMENSION_LABELS}
      onChange={setDimension}
    />
  );
  return (
    <>
      <ThinWindowNudge sundays={shown.length} />
      {/* One message instead of a page of empty charts; the all-Sundays chart below still shows. */}
      {shown.length > 0 && (
        <>
          <ConditionsExplorer events={shown} explainer={explainers['conditions']} />
          <ChartFrame
            title="Difficulty and weather"
            subtitle={
              effects.data?.model
                ? `Line: club model over all ${effects.data.model.n_events} Sundays (positive = harder)`
                : 'Not enough Sundays with weather for a club model yet (positive = harder)'
            }
            option={fit.option}
            columns={fit.data.columns}
            rows={fit.data.rows}
            csvName="weather-difficulty"
            ariaLabel="Scatter plot of event difficulty against the chosen weather measure"
            urlKey="wf"
            zoom="xy"
            full={fitFull}
            explainer={explainers['wf']}
            controls={
              <Picker
                label="Weather measure"
                value={covariate}
                options={MODEL_COVARIATES}
                labels={COVARIATE_LABELS}
                onChange={setCovariate}
              />
            }
          />
          <ChartFrame
            title="Wind rose"
            subtitle="Mean field median by the direction the wind came from"
            option={rose.option}
            columns={rose.data.columns}
            rows={rose.data.rows}
            csvName="weather-wind-rose"
            ariaLabel="Polar bar chart of mean field median by wind direction"
            urlKey="wr"
            zoom="none"
            full={roseFull}
            explainer={explainers['wr']}
          />
          {effects.data ? (
            <ChartFrame
              title="Scores by conditions"
              subtitle="Mean score of every round shot in each band"
              {...chartProps(bandScoreChart(effects.data.bands, dimension))}
              csvName="weather-scores-by-band"
              ariaLabel="Bar chart of mean score per weather band"
              urlKey="wb"
              fullQuery={bandFullQuery}
              explainer={explainers['wb']}
              controls={dimensionPicker('Group scores by')}
            />
          ) : (
            <Pending isError={effects.isError} what="weather effects" />
          )}
          {turnout.data ? (
            <ChartFrame
              title="Turnout by conditions"
              subtitle="Mean head count in each band"
              {...chartProps(turnoutChart(turnout.data, dimension))}
              csvName="weather-turnout"
              ariaLabel="Bar chart of mean head count per weather band"
              urlKey="wt"
              fullQuery={turnoutFullQuery}
              explainer={explainers['wt']}
              controls={dimensionPicker('Group turnout by')}
            />
          ) : (
            <Pending isError={turnout.isError} what="turnout" />
          )}
        </>
      )}
      {sensitivityModel ? (
        <ChartFrame
          title="Weather sensitivity"
          subtitle="Targets gained or lost per step of weather, all Sundays"
          // A flat measure has nothing to draw: an empty, thin chart sits under the note, and
          // the Table and CSV still list every shooter.
          option={sensitivityModel.flat ? {} : sensitivityModel.option}
          columns={sensitivityModel.data.columns}
          rows={sensitivityModel.data.rows}
          csvName="weather-sensitivity"
          ariaLabel={
            sensitivityModel.flat
              ? `No weather sensitivity to show for ${SENSITIVITY_NOUNS[sensitivityCovariate]}`
              : "Bar chart of each shooter's weather sensitivity"
          }
          urlKey="ws"
          zoom="none"
          full={sensitivityFull}
          fullscreen={!sensitivityModel.flat}
          height={sensitivityModel.flat ? 8 : 320}
          explainer={explainers['ws']}
          controls={
            <>
              <Picker
                label="Sensitivity to"
                value={sensitivityCovariate}
                options={SENSITIVITY_COVARIATES}
                labels={SENSITIVITY_LABELS}
                onChange={setSensitivityCovariate}
              />
              {sensitivityModel.flat && (
                <p className="min-w-0 basis-full text-text-muted">
                  No one&apos;s scores move with {SENSITIVITY_NOUNS[sensitivityCovariate]} more than
                  chance would explain. With the rounds we have, everyone&apos;s estimate for{' '}
                  {SENSITIVITY_NOUNS[sensitivityCovariate]} rounds to zero.
                </p>
              )}
            </>
          }
        />
      ) : (
        <Pending isError={sensitivity.isError} what="weather sensitivity" />
      )}
    </>
  );
}

function chartProps(chart: ReturnType<typeof bandScoreChart>) {
  return { option: chart.option, columns: chart.data.columns, rows: chart.data.rows };
}

export function WeatherPage() {
  const events = useWeatherEvents();
  const { range } = useTimeWindow();
  const meta = useMeta();
  return (
    <main className="flex flex-col gap-4 p-4">
      <h1 className="text-2xl font-bold">Weather</h1>
      {events.isPending || events.isError ? (
        <Pending isError={events.isError} what="weather" />
      ) : events.data.length === 0 ? (
        <section aria-label="No weather data yet" className="rounded-card bg-elevated p-4">
          <h2 className="text-lg font-medium">No weather data yet</h2>
          <p className="text-text-muted">
            Weather for each Sunday is fetched after the shoot. These charts appear once events have
            weather.
          </p>
        </section>
      ) : range === null ? (
        // The window is anchored on the latest scored Sunday: no answer (error) or none (fresh
        // install) must not read as "Loading…" for ever.
        meta.isPending ? (
          <Pending isError={false} what="weather" />
        ) : meta.isError ? (
          <Pending isError what="the time window" />
        ) : (
          <section aria-label="No scored Sundays yet" className="rounded-card bg-elevated p-4">
            <h2 className="text-lg font-medium">No scored Sundays yet</h2>
            <p className="text-text-muted">
              The time window counts back from the latest Sunday with scores, so these charts appear
              once scores are in.
            </p>
          </section>
        )
      ) : (
        <WeatherCharts events={events.data} range={range} />
      )}
    </main>
  );
}
