import { useId, useMemo, useState } from 'react';
import { Link } from 'react-router';
import type { components } from '../../../api/schema';
import { ThinWindowNudge } from '../../../components/ThinWindowNudge';
import { PageTopSlot } from '../../../components/layout/pageTop';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { AboutBlock } from '../../../components/ui/AboutBlock';
import type { ChartFull, TabularData } from '../../../components/charts/types';
import { useRoundTypeHref, useRoundTypes } from '../../../lib/roundTypes';
import { api, unwrap } from '../../../api/client';
import { formatShortDate } from '../../../lib/format';
import { enumCodec, stringCodec, useUrlState } from '../../../lib/useUrlState';
import type { EraSel } from '../api';
import { CoverageNote, ScopeLine } from '../CoverageNote';
import { inPeriod, useStationWindow } from '../window';
import { AllSetupsButton } from '../EraToggle';
import { useStation, useStations } from '../api';
import {
  gustLabel,
  HEATMAP_MIN_ROUNDS,
  eraBarOption,
  heatmapOption,
  hitPctBarOption,
  windBarOption,
  difficultyLineOption,
} from '../chartOptions';
import { EraToggle, ToggleButton } from '../EraToggle';
import { explainers } from '../explainers';
import { pct, percentValue } from '../format';
import { StackedTable } from '../StackedTable';

type StationStatOut = components['schemas']['StationStatOut'];
type StationDetailOut = components['schemas']['StationDetailOut'];
type StationShooterCellOut = components['schemas']['StationShooterCellOut'];

/** `?era=all` (absent = current) and `?st=<label>` such as `7` or `7A` (C10 URL state; invalid → default). */
const ERA_CODEC = enumCodec<EraSel>(['current', 'all']);
const NO_STATION = '';

const STATION_COLUMNS: TabularData['columns'] = [
  { key: 'station', label: 'Station', type: 'string' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'ci_low', label: 'Likely range low', type: 'number' },
  { key: 'ci_high', label: 'Likely range high', type: 'number' },
  { key: 'n_targets', label: 'Targets', type: 'int' },
  { key: 'n_rounds', label: 'Rounds', type: 'int' },
  { key: 'n_events', label: 'Sundays', type: 'int' },
];
const EVENT_COLUMNS: TabularData['columns'] = [
  { key: 'date', label: 'Sunday', type: 'date' },
  { key: 'station', label: 'Station', type: 'string' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'n_targets', label: 'Targets', type: 'int' },
];
const MATRIX_COLUMNS: TabularData['columns'] = [
  { key: 'shooter', label: 'Shooter', type: 'string' },
  { key: 'station', label: 'Station', type: 'string' },
  { key: 'hit_pct', label: 'Hit %', type: 'string' },
  { key: 'n_targets', label: 'Targets', type: 'int' },
  { key: 'n_rounds', label: 'Rounds', type: 'int' },
];
const ERA_COLUMNS: TabularData['columns'] = [
  { key: 'era', label: 'Era', type: 'string' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'n_targets', label: 'Targets', type: 'int' },
  { key: 'n_events', label: 'Sundays', type: 'int' },
];
const WIND_COLUMNS: TabularData['columns'] = [
  { key: 'band', label: 'Gust band', type: 'string' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'n_events', label: 'Sundays', type: 'int' },
  { key: 'sufficient', label: 'Enough Sundays', type: 'string' },
];

/** Leaders listed before "Show all N". */
const LEADERS_SHOWN = 10;

const hasSquare = (c: StationShooterCellOut): boolean => c.n_rounds >= HEATMAP_MIN_ROUNDS;

/** One row per shooter (22 px each) so labels stay readable however many shooters shot. */
function matrixHeight(cells: StationShooterCellOut[]): number {
  const shooters = new Set(cells.filter(hasSquare).map((c) => c.shooter_id)).size;
  return Math.min(1600, Math.max(320, shooters * 22 + 96));
}

function eraLabel(stat: StationStatOut): string {
  return stat.era_start === null ? 'Original setup' : `Since ${stat.era_start}`;
}

type StationEventPctOut = components['schemas']['StationEventPctOut'];

function trendOptionOf(events: StationEventPctOut[]) {
  return difficultyLineOption(
    events.map((e) => ({ date: e.event_date, station: e.label, hitPct: e.hit_pct })),
  );
}

function eventRows(events: StationEventPctOut[]) {
  return events.map((e) => ({
    date: e.event_date,
    station: e.label,
    hit_pct: percentValue(e.hit_pct),
    n_targets: e.n_targets,
  }));
}

function SummaryTable({ stations }: { stations: StationStatOut[] }) {
  return (
    <section aria-label="Station summary section" className="flex min-w-0 flex-col gap-1">
      <AboutBlock explainer={explainers['station-summary']} />
      <StackedTable
        caption="Station summary"
        headers={[
          'Station',
          'Hit %',
          'Likely range',
          'Clean rate',
          'Rounds',
          'Sundays',
          'Separator',
        ]}
        rows={stations.map((s) => ({
          key: s.label,
          header: `Station ${s.label}`,
          cells: [
            pct(s.hit_pct),
            s.ci_low === null || s.ci_high === null ? '—' : `${pct(s.ci_low)}–${pct(s.ci_high)}`,
            pct(s.clean_rate),
            s.n_rounds,
            s.n_events,
            s.separator === null ? '—' : s.separator.toFixed(2),
          ],
        }))}
      />
    </section>
  );
}

function StationDetail({
  detail,
  era,
  when,
}: {
  detail: StationDetailOut;
  era: EraSel;
  /** "in the last 8 weeks", or "so far" for the whole history. */
  when: string;
}) {
  const no = detail.label;
  const leadersId = useId();
  // Leader links keep the global round-type filter (C10).
  const href = useRoundTypeHref();
  const [allLeaders, setAllLeaders] = useState(false);
  // A tie at the cut: leaders are ranked by hit %, so the tied ones sit right after the tenth.
  const cutPct = detail.leaders[LEADERS_SHOWN - 1]?.hit_pct;
  const tiedMore = detail.leaders.slice(LEADERS_SHOWN).filter((l) => l.hit_pct === cutPct).length;
  const leaders = allLeaders ? detail.leaders : detail.leaders.slice(0, LEADERS_SHOWN);
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <ChartFrame
        title={`Station ${no} eras`}
        subtitle="Hit % in each setup, split on the dates the station was reset"
        option={eraBarOption(detail.eras.map((e) => ({ label: eraLabel(e), hitPct: e.hit_pct })))}
        columns={ERA_COLUMNS}
        rows={detail.eras.map((e) => ({
          era: eraLabel(e),
          hit_pct: percentValue(e.hit_pct),
          n_targets: e.n_targets,
          n_events: e.n_events,
        }))}
        csvName={`station-${no}-eras`}
        ariaLabel={`Bar chart of station ${no} hit % by era`}
        urlKey="stera"
        zoom="none"
        explainer={explainers.stera}
      />
      {detail.wind.length === 0 ? (
        <ThinWindowNudge
          sundays={0}
          label="Widen the time window"
          message={`No weather data for station ${no} ${when}.`}
        />
      ) : (
        <ChartFrame
          title={`Wind × station ${no}`}
          subtitle={`Hit % by gust strength, ${era === 'current' ? 'current setup' : 'all setups'}; grey bars rest on fewer than 5 Sundays`}
          option={windBarOption(
            detail.wind.map((w) => ({
              band: w.band,
              hitPct: w.hit_pct,
              nEvents: w.n_events,
              sufficient: w.sufficient,
            })),
          )}
          columns={WIND_COLUMNS}
          rows={detail.wind.map((w) => ({
            band: gustLabel(w.band),
            hit_pct: percentValue(w.hit_pct),
            n_events: w.n_events,
            sufficient: w.sufficient ? 'yes' : 'no',
          }))}
          csvName={`station-${no}-wind`}
          ariaLabel={`Bar chart of station ${no} hit % by gust band`}
          urlKey="stwind"
          zoom="none"
          explainer={explainers.stwind}
        />
      )}
      <section aria-labelledby={leadersId} className="flex min-w-0 flex-col gap-2">
        <h3 id={leadersId} className="font-medium">
          Station {no} leaders
        </h3>
        <AboutBlock explainer={explainers['station-leaders']} label="About these leaders" />
        {detail.leaders.length === 0 ? (
          <ThinWindowNudge
            sundays={0}
            label="Widen the time window"
            message={`Nobody has shot station ${no} three times ${when}.`}
          />
        ) : (
          <ol className="flex flex-col gap-1">
            {leaders.map((leader) => (
              <li
                key={leader.shooter_id}
                className="flex min-h-11 flex-wrap items-center justify-between gap-x-3"
              >
                <Link
                  to={href(`/shooters/${leader.shooter_id}`)}
                  className="inline-flex min-h-11 min-w-11 items-center underline underline-offset-2"
                >
                  {leader.display_name}
                </Link>
                <span className="text-sm text-text-muted">
                  {pct(leader.hit_pct)} · {leader.n_rounds} rounds
                </span>
              </li>
            ))}
          </ol>
        )}
        {detail.leaders.length > LEADERS_SHOWN && (
          <div className="flex flex-wrap items-center gap-x-3">
            <button
              type="button"
              aria-expanded={allLeaders}
              onClick={() => {
                setAllLeaders((v) => !v);
              }}
              className="min-h-11 self-start rounded-button px-1 text-sm text-accent underline underline-offset-2"
            >
              {allLeaders ? 'Show fewer' : `Show all ${String(detail.leaders.length)}`}
            </button>
            {!allLeaders && tiedMore > 0 && (
              <span className="text-sm text-text-muted">
                {String(tiedMore)} more tied at {pct(cutPct ?? null)}
              </span>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

/** An insight's station labels (`5`, `7A`) as the chart's `St {label}` categories (Plan 12). */
export function stationLabels(keys: readonly string[]): string[] {
  return keys.map((k) => (k.startsWith('St ') ? k : `St ${k}`));
}

export function StationsPage() {
  const detailId = useId();
  const [era, setEra] = useUrlState<EraSel>('era', ERA_CODEC, 'current');
  const [requested, setRequested] = useUrlState('st', stringCodec, NO_STATION);
  const overview = useStations(era);
  const tw = useStationWindow();
  const when = inPeriod(tw.window);
  const [roundTypes] = useRoundTypes();
  const labelList = overview.data?.stations.map((s) => s.label) ?? [];
  const wanted = requested.trim().toUpperCase();
  const selected = labelList.includes(wanted) ? wanted : (labelList[0] ?? null);
  const detail = useStation(selected, era);

  const byEvent = overview.data?.by_event;
  const trendOption = useMemo(() => trendOptionOf(byEvent ?? []), [byEvent]);

  // Fullscreen and the CSV of the trend chart go beyond the window: every Sunday with a sheet.
  const trendFull = {
    queryKey: ['/api/stations', 'chart-full', era, roundTypes],
    queryFn: async (): Promise<ChartFull> => {
      const all = await unwrap(
        api.GET('/api/stations', { params: { query: { era, round_type: roundTypes } } }),
      );
      return {
        option: trendOptionOf(all.by_event),
        rows: eventRows(all.by_event),
        note: 'Every Sunday with a station sheet, whatever the time window.',
      };
    },
  };

  if (tw.failed || overview.isError) return <p role="alert">Could not load station data.</p>;
  if (overview.isPending) return <p role="status">Loading stations…</p>;
  const data = overview.data;

  return (
    <div className="flex min-w-0 flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Stations</h1>
        <EraToggle era={era} onChange={setEra} resetDate={data.last_reset_date} />
      </header>
      <ScopeLine era={era} />
      <PageTopSlot page="stations" />
      {data.stations.length === 0 ? (
        data.coverage.latest_date === null ? (
          <p className="text-text-muted">No station data for this filter.</p>
        ) : data.coverage.n_station_sundays > 0 ? (
          <ThinWindowNudge
            sundays={0}
            label="Show every setup"
            message={`No station sheets since the last reset ${when}.`}
            action={<AllSetupsButton onClick={() => setEra('all')} />}
          />
        ) : (
          <ThinWindowNudge
            sundays={0}
            label="Widen the time window"
            message={`No station sheets ${when} (latest: ${formatShortDate(data.coverage.latest_date)}).`}
          />
        )
      ) : (
        <>
          <CoverageNote coverage={data.coverage} filtered={roundTypes.length > 0} />
          <SummaryTable stations={data.stations} />
          <ChartFrame
            title="Hit % by station"
            subtitle="Share of targets broken at each station, with a likely range"
            option={hitPctBarOption(
              data.stations.map((s) => ({
                station: s.label,
                hitPct: s.hit_pct,
                ciLow: s.ci_low,
                ciHigh: s.ci_high,
              })),
            )}
            columns={STATION_COLUMNS}
            rows={data.stations.map((s) => ({
              station: s.label,
              hit_pct: percentValue(s.hit_pct),
              ci_low: percentValue(s.ci_low),
              ci_high: percentValue(s.ci_high),
              n_targets: s.n_targets,
              n_rounds: s.n_rounds,
              n_events: s.n_events,
            }))}
            csvName="station-hit-pct"
            ariaLabel="Bar chart of hit % by station"
            urlKey="sthit"
            zoom="none"
            explainer={explainers.sthit}
            hlLabels={stationLabels}
          />
          <ChartFrame
            title="Hit % over time"
            subtitle="Hit % per station on each Sunday; lower means a harder station"
            option={trendOption}
            columns={EVENT_COLUMNS}
            rows={eventRows(data.by_event)}
            fullQuery={trendFull}
            csvName="station-difficulty"
            ariaLabel="Line chart of station hit % over time"
            urlKey="sttime"
            zoom="x"
            explainer={explainers.sttime}
          />
          {data.matrix.some(hasSquare) ? (
            <ChartFrame
              title="Shooter × station"
              subtitle="Each shooter’s hit % at each station (3 or more rounds)"
              option={heatmapOption(
                data.matrix.map((c) => ({
                  shooter: c.display_name,
                  station: c.label,
                  hitPct: c.hit_pct,
                  nRounds: c.n_rounds,
                })),
              )}
              columns={MATRIX_COLUMNS}
              rows={data.matrix.map((c) => ({
                shooter: c.display_name,
                station: c.label,
                // Under 3 rounds there is no square; the table says so instead of a number.
                hit_pct: hasSquare(c) ? pct(c.hit_pct) : 'not enough rounds yet',
                n_targets: c.n_targets,
                n_rounds: c.n_rounds,
              }))}
              csvName="shooter-station-matrix"
              ariaLabel="Heatmap of hit % by shooter and station"
              urlKey="stmatrix"
              zoom="none"
              height={matrixHeight(data.matrix)}
              explainer={explainers.stmatrix}
            />
          ) : (
            <ThinWindowNudge
              sundays={0}
              label="Widen the time window"
              message={`Nobody has shot any station three times ${when}.`}
            />
          )}
          <section aria-labelledby={detailId} className="flex flex-col gap-3">
            <h2 id={detailId} className="text-lg font-medium">
              Station detail
            </h2>
            <div role="group" aria-label="Choose a station" className="flex flex-wrap gap-2">
              {labelList.map((label) => (
                <ToggleButton
                  key={label}
                  active={label === selected}
                  onClick={() => {
                    setRequested(label);
                  }}
                >
                  Station {label}
                </ToggleButton>
              ))}
            </div>
            {detail.isPending ? (
              <p role="status">Loading station {selected}…</p>
            ) : detail.isError ? (
              <p role="alert">Could not load station {selected}.</p>
            ) : (
              <StationDetail
                key={`${detail.data.label}|${era}|${tw.window}`}
                detail={detail.data}
                era={era}
                when={when}
              />
            )}
          </section>
        </>
      )}
    </div>
  );
}
