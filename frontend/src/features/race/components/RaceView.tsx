import { Pause, Play } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import { bumpOption } from '../../../components/charts/builders/bump';
import { raceOption } from '../../../components/charts/builders/race';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { shooterLabels, useChartTarget } from '../../../components/charts/chartTarget';
import type { ChartFull } from '../../../components/charts/types';
import { useRoundTypes } from '../../../lib/roundTypes';
import {
  fetchHistory,
  historyQuery,
  type HistoryFrame,
  type LeaderboardMetric,
  type RaceParams,
} from '../api';
import { raceExplainer } from '../explainers';
import {
  BUMP_FULLSCREEN_TOP,
  formatEventDate,
  formatValue,
  metricLabel,
  RACE_FULL_TOP,
  RACE_FULLSCREEN_TOP,
  RACE_TOP,
  type RaceMode,
} from '../labels';
import { bumpTable, frameTable, racerNames, toLeaderboardFrame } from '../transforms';
import { PLAY_INTERVAL_MS, usePlayer } from '../usePlayer';

const hlLabels = shooterLabels('display_name');

export interface RaceViewProps {
  frames: readonly HistoryFrame[];
  metric: LeaderboardMetric;
  mode: RaceMode;
  /** The race's period, dates and measure: the full-data fetch asks for the same frames with everyone in them. */
  query: RaceParams;
}

export function RaceView({ frames, metric, mode, query }: RaceViewProps) {
  // An insight link opens the race on its Sunday (`race-bars.at`).
  const { target } = useChartTarget('race-bars');
  const at = frames.findIndex((f) => f.event_date === target.params.at);
  const player = usePlayer(frames.length, PLAY_INTERVAL_MS, at === -1 ? null : at);
  const frame = frames[player.index];
  const label = metricLabel(metric);
  // Builders draw from Plan 07's LeaderboardFrame; ChartFrame's table and CSV use the TabularData versions.
  // Names are fixed across the whole race, so a bar is never renamed mid-race.
  const names = useMemo(() => racerNames(frames), [frames]);
  const bump = useMemo(() => bumpTable(frames, names), [frames, names]);
  const bumpChart = useMemo(
    () =>
      bumpOption(
        frames.map((f) => toLeaderboardFrame(f, names)),
        { top: RACE_TOP },
      ),
    [frames, names],
  );
  const raceChart = useMemo(
    () =>
      frame === undefined ? {} : raceOption(toLeaderboardFrame(frame, names), { top: RACE_TOP }),
    [frame, names],
  );
  const queryClient = useQueryClient();
  const [roundTypes] = useRoundTypes();
  const { period, from, to } = query;
  // One fetch of every ranked shooter on every Sunday feeds both charts' fullscreen and CSV.
  const raw = useMemo(() => {
    const params = historyQuery(roundTypes, { period, metric, from, to }, RACE_FULL_TOP);
    return {
      queryKey: ['/api/leaderboards/history', params] as const,
      queryFn: () => fetchHistory(params),
    };
  }, [roundTypes, period, metric, from, to]);
  const eventDate = frame?.event_date;
  const barsFullQuery = useMemo(
    () => ({
      queryKey: [...raw.queryKey, 'chart-full', 'race-bars', eventDate],
      queryFn: async (): Promise<ChartFull> => {
        const all = await queryClient.ensureQueryData(raw);
        const fullFrame = all.frames.find((f) => f.event_date === eventDate);
        if (fullFrame === undefined) return {};
        const fullNames = racerNames(all.frames);
        return {
          option: raceOption(toLeaderboardFrame(fullFrame, fullNames), {
            top: RACE_FULLSCREEN_TOP,
          }),
          rows: frameTable(fullFrame, label, fullNames).rows,
          height: Math.max(720, 80 + 28 * Math.min(RACE_FULLSCREEN_TOP, fullFrame.rows.length)),
          note: `The top ${String(RACE_FULL_TOP)} ranked that Sunday.`,
          // The full frames cover the same replay dates as the card, so the tag keeps naming them.
          scope: 'windowed',
        };
      },
    }),
    [raw, queryClient, eventDate, label],
  );
  const bumpFullQuery = useMemo(
    () => ({
      queryKey: [...raw.queryKey, 'chart-full', 'race-bump'],
      queryFn: async (): Promise<ChartFull> => {
        const all = await queryClient.ensureQueryData(raw);
        const fullNames = racerNames(all.frames);
        return {
          option: bumpOption(
            all.frames.map((f) => toLeaderboardFrame(f, fullNames)),
            { top: BUMP_FULLSCREEN_TOP },
          ),
          rows: bumpTable(all.frames, fullNames).rows,
          note: `The top ${String(RACE_FULL_TOP)} ranked on every Sunday.`,
          scope: 'windowed',
        };
      },
    }),
    [raw, queryClient],
  );
  if (frame === undefined) return null;
  const race = frameTable(frame, label, names);
  const last = Math.max(0, frames.length - 1);

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-elevated p-3">
        <button
          type="button"
          onClick={player.playing ? player.pause : player.play}
          className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button bg-primary px-4"
        >
          {player.playing ? <Pause aria-hidden size={18} /> : <Play aria-hidden size={18} />}
          {player.playing ? 'Pause' : 'Play'}
        </button>
        <input
          type="range"
          min={0}
          max={last}
          step={1}
          value={player.index}
          aria-label="Race position"
          aria-valuetext={formatEventDate(frame.event_date)}
          onChange={(event) => {
            player.seek(Number(event.currentTarget.value));
          }}
          className="order-last min-h-11 w-full min-w-0 accent-primary md:order-none md:w-auto md:flex-1"
        />
        <output
          aria-live={player.playing ? 'off' : 'polite'}
          className="ml-auto min-w-28 text-right font-medium md:ml-0"
        >
          {formatEventDate(frame.event_date)}
        </output>
      </div>
      <ChartFrame
        title={label}
        subtitle={`Race after ${formatEventDate(frame.event_date)}`}
        option={raceChart}
        columns={race.columns}
        rows={race.rows}
        fullQuery={barsFullQuery}
        csvName={`race-${metric}-${frame.event_date}`}
        ariaLabel={`${label} race bar chart`}
        urlKey="race-bars"
        explainer={raceExplainer('race-bars', mode)}
        zoom="none"
        hlLabels={hlLabels}
      />
      <ol aria-label="Standings" className="flex flex-col text-sm">
        {frame.rows.map((row) => (
          <li
            key={row.shooter_id}
            className="flex min-h-11 items-center justify-between gap-3 border-t border-outline-variant"
          >
            <span className="min-w-0 break-words">
              <span className="mr-2 tabular-nums text-text-muted">{row.rank}</span>
              {names.get(row.shooter_id) ?? row.display_name}
            </span>
            <span className="tabular-nums">{formatValue(metric, row.value)}</span>
          </li>
        ))}
      </ol>
      <ChartFrame
        title="Rank over time"
        option={bumpChart}
        columns={bump.columns}
        rows={bump.rows}
        fullQuery={bumpFullQuery}
        csvName={`race-ranks-${metric}`}
        ariaLabel={`${label} rank bump chart`}
        urlKey="race-bump"
        explainer={raceExplainer('race-bump', mode)}
      />
    </div>
  );
}
