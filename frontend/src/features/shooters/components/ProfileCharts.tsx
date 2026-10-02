import { useQueryClient } from '@tanstack/react-query';
import { useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { shotDateOf } from '../../../components/charts/builders/sundayCalendar';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { useChartTarget, useTargetWindow } from '../../../components/charts/chartTarget';
import { querySpec, useExplore } from '../../../components/charts/explore';
import type { ChartFull, ChartFullQuery, TabularRow } from '../../../components/charts/types';
import { Chip } from '../../../components/ui/Chip';
import { useRoundTypeHref, useRoundTypes } from '../../../lib/roundTypes';
import {
  filterRowsByWindow,
  useMeta,
  useTimeWindow,
  type WindowRange,
} from '../../../lib/timeWindow';
import { rangeText, windowPhrase } from '../../../lib/windowText';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { enumCodec, intCodec, useUrlState } from '../../../lib/useUrlState';
import {
  fetchAllClubDistribution,
  fetchAllSplits,
  fetchHeldSundays,
  useClubDistribution,
  useHeldSundays,
  useShooterInsights,
  useShooterRating,
  useShooterRounds,
  useShooterSpecials,
  useShooterSplits,
} from '../api';
import type { ShooterRound, SplitBy } from '../api';
import {
  TREND_LINES,
  TREND_LINE_LABELS,
  activeYears,
  attendanceModel,
  distributionModel,
  finishesModel,
  isFinish,
  learningCurveModel,
  monthsModel,
  ratingModel,
  splitsModel,
  toughDaysModel,
  trendModel,
  type TrendLine,
} from '../charts';
import { explainers } from '../explainers';
import { AllRoundTypesTag } from './InlineExplainer';
import { QueryChart } from './QueryChart';

const SPLIT_LABELS: Record<SplitBy, string> = {
  year: 'Year',
  season: 'Time of year',
  month: 'Month',
  round_type: 'Round type',
  gauge: 'Gauge',
  temp_band: 'Temperature',
  wind_band: 'Wind',
  precip_band: 'Rain',
};
const SPLITS = Object.keys(SPLIT_LABELS) as SplitBy[];
/** Table-row drill link to the event on the row's date column. */
const eventHref = (key: string) => (row: TabularRow) => `/events/${String(row[key])}`;
/** 12 month rows plus the axis name and the colour scale: the same on a phone and on desktop. */
const CALENDAR_HEIGHT = 440;
/** An empty window on a personal chart: "No rounds in the last 8 weeks. Last shot Aug 2, 2026." */
const NO_ROUNDS = { none: 'No rounds', last: 'Last shot' };
const splitCodec = enumCodec(SPLITS); // an unknown ?split= reads as the default 'year'

/**
 * True while the header window is still being worked out (waiting on the latest Sunday). Charts
 * that zoom to the window hold their loading placeholder until then, so they never flash every
 * round and then jump. If the lookup fails they show unzoomed rather than load forever.
 */
function useWindowPending(): boolean {
  const { range } = useTimeWindow();
  const meta = useMeta();
  // A failed lookup stays failed: TanStack reports a refetch of a never-succeeded query as
  // `pending` again, so `isPending` alone would flip the charts to skeletons and back in a loop.
  return range === null && meta.isPending && meta.errorUpdateCount === 0;
}

function RatingChart({ shooterId }: { shooterId: number }) {
  const query = useShooterRating(shooterId);
  const { range } = useTimeWindow();
  const pending = useWindowPending();
  return (
    <QueryChart
      title="Rating"
      query={query}
      waiting={pending}
      isEmpty={(d) => d.points.length === 0}
      emptyText="No rating yet"
    >
      {(rating) => {
        const m = ratingModel(rating.points);
        return (
          <ChartFrame
            title="Rating"
            subtitle="Skill estimate with its likely range; the pin marks the peak"
            option={m.option}
            window={range}
            emptyWindow={NO_ROUNDS}
            columns={m.columns}
            rows={m.rows}
            csvName={`rating-${shooterId}`}
            ariaLabel="Rating over time with likely range"
            urlKey="rating"
            controls={<AllRoundTypesTag />}
            explainer={explainers.rating}
            rowHref={eventHref('event_date')}
            rowHrefKey="event_date"
          />
        );
      }}
    </QueryChart>
  );
}

/** `trend.line`: the insight line over the scores (Plan 12); absent = none. */
const lineCodec = {
  parse: (raw: string): TrendLine | 'none' | null =>
    raw === 'none' || (TREND_LINES as readonly string[]).includes(raw)
      ? (raw as TrendLine | 'none')
      : null,
  serialize: (v: TrendLine | 'none') => v,
};

function TrendChart({ shooterId }: { shooterId: number }) {
  const query = useShooterRounds(shooterId);
  const { range } = useTimeWindow();
  const pending = useWindowPending();
  const [line, setLine] = useUrlState<TrendLine | 'none'>('trend.line', lineCodec, 'none');
  const chips = (
    <div role="group" aria-label="Line" className="flex flex-wrap gap-2">
      {(['none', ...TREND_LINES] as const).map((l) => (
        <Chip key={l} selected={l === line} onClick={() => setLine(l)}>
          {l === 'none' ? 'No line' : TREND_LINE_LABELS[l]}
        </Chip>
      ))}
    </div>
  );
  return (
    <QueryChart
      title="Scores over time"
      query={query}
      waiting={pending}
      isEmpty={(d) => d.length === 0}
      emptyText="No rounds yet"
      controls={chips}
    >
      {(rounds) => {
        const m = trendModel(rounds, line === 'none' ? null : line);
        return (
          <ChartFrame
            title="Scores over time"
            subtitle="Your score, and your score minus the day's middle score; pins mark personal bests"
            option={m.option}
            window={range}
            emptyWindow={NO_ROUNDS}
            columns={m.columns}
            rows={m.rows}
            csvName={`scores-${shooterId}`}
            ariaLabel="Scores and scores against the day's middle score per round"
            urlKey="trend"
            explainer={explainers.trend}
            rowHref={eventHref('event_date')}
            rowHrefKey="event_date"
            controls={chips}
          />
        );
      }}
    </QueryChart>
  );
}

function FinishesChart({ shooterId }: { shooterId: number }) {
  const query = useShooterRounds(shooterId);
  const { range } = useTimeWindow();
  const pending = useWindowPending();
  return (
    <QueryChart
      title="Finishes"
      query={query}
      waiting={pending}
      isEmpty={(d) => !d.some(isFinish)}
      emptyText="No finishes yet"
    >
      {(rounds) => {
        const m = finishesModel(rounds);
        return (
          <ChartFrame
            title="Finishes"
            subtitle="Your place on each Sunday with full results"
            option={m.option}
            window={range}
            emptyWindow={NO_ROUNDS}
            columns={m.columns}
            rows={m.rows}
            csvName={`finishes-${shooterId}`}
            ariaLabel="Place on each Sunday"
            urlKey="finishes"
            explainer={explainers.finishes}
            rowHref={eventHref('event_date')}
            rowHrefKey="event_date"
          />
        );
      }}
    </QueryChart>
  );
}

/** Says which window came up empty and where to widen it (the header filter's 12M and All). */
function EmptyWindow({ title, what }: { title: string; what: string }) {
  const { window, range } = useTimeWindow();
  return (
    <Card title={title}>
      <EmptyState
        title={`No ${what} in ${windowPhrase(window, range)}`}
        description="Pick 12M or All in the time filter above to see more."
      />
    </Card>
  );
}

function DistributionChart({ shooterId }: { shooterId: number }) {
  const rounds = useShooterRounds(shooterId);
  const { range } = useTimeWindow();
  const club = useClubDistribution(range);
  const [roundTypes] = useRoundTypes();
  const queryClient = useQueryClient();
  const allRounds = rounds.data;
  // Fullscreen and the CSV cover every round and every year, not just the window.
  const fullQuery = useMemo<ChartFullQuery | undefined>(
    () =>
      allRounds === undefined
        ? undefined
        : {
            queryKey: ['/api/shooters/{id}/distribution', shooterId, roundTypes, 'chart-full'],
            queryFn: async () => {
              const m = distributionModel(
                allRounds,
                await fetchAllClubDistribution(queryClient, roundTypes),
              );
              return {
                option: m.option,
                columns: m.columns,
                rows: m.rows,
                note: 'Every round you have shot, next to every club round. The card shows the time window.',
              };
            },
          },
    [allRounds, shooterId, roundTypes, queryClient],
  );
  const title = 'Score distribution vs club';
  return (
    <QueryChart
      title={title}
      query={rounds}
      isEmpty={(d) => d.length === 0}
      emptyText="No rounds yet"
    >
      {(every) => (
        <QueryChart title={title} query={club} isEmpty={() => false} emptyText="">
          {(groups) => {
            // The club query only runs once the window's dates are known, so `range` is set here.
            const mine = filterRowsByWindow(every, 'event_date', range as WindowRange);
            if (mine.length === 0) return <EmptyWindow title={title} what="rounds" />;
            const m = distributionModel(mine, groups);
            return (
              <ChartFrame
                title={title}
                subtitle="Share of rounds at each score, next to the club"
                option={m.option}
                columns={m.columns}
                rows={m.rows}
                csvName={`distribution-${shooterId}`}
                ariaLabel="Score distribution compared with the club"
                urlKey="dist"
                explainer={explainers.dist}
                fullQuery={fullQuery}
              />
            );
          }}
        </QueryChart>
      )}
    </QueryChart>
  );
}

function LearningCurveChart({ shooterId }: { shooterId: number }) {
  const query = useShooterInsights(shooterId);
  return (
    <QueryChart
      title="Learning curve vs club"
      query={query}
      isEmpty={(d) => d.learning_curve.length === 0}
      emptyText="Not enough Sundays for a learning curve"
    >
      {(insights) => {
        const m = learningCurveModel(insights.learning_curve);
        return (
          <ChartFrame
            title="Learning curve vs club"
            subtitle={`Score vs the day's middle score, by your Sunday number${
              m.clubHidden
                ? '. Club line hidden where fewer than 3 shooters (not enough rounds yet)'
                : ''
            } · all years`}
            option={m.option}
            columns={m.columns}
            rows={m.rows}
            csvName={`learning-${shooterId}`}
            ariaLabel="Learning curve compared with the club"
            urlKey="learn"
            controls={<AllRoundTypesTag />}
            explainer={explainers.learn}
          />
        );
      }}
    </QueryChart>
  );
}

function SplitsChart({ shooterId }: { shooterId: number }) {
  const [by, setBy] = useUrlState('split', splitCodec, 'year');
  const { window: choice, range } = useTimeWindow();
  const query = useShooterSplits(shooterId, by, range);
  const [roundTypes] = useRoundTypes();
  const queryClient = useQueryClient();
  // The previous split stays on screen while the next loads, so the title follows the data shown.
  const [shownBy, setShownBy] = useState(by);
  if (!query.isPlaceholderData && shownBy !== by) setShownBy(by);
  const label = SPLIT_LABELS[shownBy];
  const chips = (
    <div role="group" aria-label="Split by" className="flex flex-wrap gap-2">
      {SPLITS.map((s) => (
        <Chip key={s} selected={s === by} onClick={() => setBy(s)}>
          {SPLIT_LABELS[s]}
        </Chip>
      ))}
    </div>
  );
  return (
    <QueryChart
      title="Splits"
      query={query}
      isEmpty={(d) => d.length === 0}
      emptyText={`No rounds in ${windowPhrase(choice, range)}. Pick 12M or All in the time filter above.`}
      controls={chips}
    >
      {(splits) => {
        const m = splitsModel(splits);
        // Fullscreen and the CSV cover every round, not just the window.
        const fullQuery: ChartFullQuery = {
          queryKey: ['/api/shooters/{id}/splits', shooterId, shownBy, roundTypes, 'chart-full'],
          queryFn: async () => {
            const every = splitsModel(
              await fetchAllSplits(queryClient, shooterId, shownBy, roundTypes),
            );
            return {
              option: every.option,
              columns: every.columns,
              rows: every.rows,
              note: 'Every round you have shot. The card shows the time window.',
            };
          },
        };
        return (
          <ChartFrame
            title={`Splits by ${label}`}
            subtitle="Average score per group; best and round counts in the table"
            option={m.option}
            columns={m.columns}
            rows={m.rows}
            csvName={`splits-${shownBy}-${shooterId}`}
            ariaLabel={`Average score by ${label.toLowerCase()}`}
            urlKey="splits"
            explainer={explainers.splits}
            fullQuery={fullQuery}
            controls={chips}
          />
        );
      }}
    </QueryChart>
  );
}

/** Both years' held Sundays and the shooter's rounds are needed before the calendar can say "missed". */
function AttendanceYear({
  shooterId,
  year,
  rounds,
  specialDates,
  yearChips,
}: {
  shooterId: number;
  year: number;
  rounds: ShooterRound[];
  specialDates: readonly string[];
  yearChips: ReactNode;
}) {
  const held = useHeldSundays(year);
  const navigate = useNavigate();
  const href = useRoundTypeHref();
  const title = `Attendance calendar ${year}`;
  const [roundTypes] = useRoundTypes();
  const queryClient = useQueryClient();
  // Every year the shooter shot, fetched only when fullscreen opens or CSV is pressed.
  const fullQuery = useMemo<ChartFullQuery>(() => {
    // Oldest year first, so the export reads chronologically.
    const years = activeYears(rounds, specialDates).sort((a, b) => a - b);
    return {
      queryKey: [
        '/api/shooters/{id}/attendance',
        shooterId,
        roundTypes,
        years,
        specialDates,
        'chart-full',
      ],
      queryFn: async () => {
        const perYear = await Promise.all(
          years.map(
            async (y) =>
              attendanceModel(
                rounds,
                await fetchHeldSundays(queryClient, y, roundTypes),
                y,
                specialDates,
              ).rows,
          ),
        );
        return {
          rows: perYear.flat(),
          note: 'Every year you shot. The chart shows the year you picked.',
        };
      },
    };
  }, [shooterId, roundTypes, rounds, specialDates, queryClient]);
  return (
    <QueryChart title={title} query={held} isEmpty={() => false} emptyText="" controls={yearChips}>
      {(heldDates) => {
        const m = attendanceModel(rounds, heldDates, year, specialDates);
        return (
          <ChartFrame
            title={title}
            subtitle="Best score on each Sunday you shot; outlined squares are Sundays you missed; ★ is a special shoot"
            option={m.option}
            columns={m.columns}
            rows={m.rows}
            csvName={`attendance-${year}-${shooterId}`}
            ariaLabel={`Attendance calendar for ${year}`}
            urlKey="cal"
            controls={yearChips}
            height={CALENDAR_HEIGHT}
            zoom="none"
            fullQuery={fullQuery}
            onEvents={{
              click: (params) => {
                const date = shotDateOf(params as { seriesName?: string; data?: unknown });
                if (date !== null) void navigate(href(`/events/${date}`));
              },
            }}
            rowHref={eventHref('date')}
            rowHrefKey="date"
            explainer={explainers.cal}
          />
        );
      }}
    </QueryChart>
  );
}

/** The calendar year a window ends in, as a window; null when the window has no start (All). */
function yearOf(window: WindowRange | null): WindowRange | null {
  if (window === null || window.from === null) return null;
  const year = window.to.slice(0, 4);
  return { from: `${year}-01-01`, to: `${year}-12-31` };
}

type CalView = 'year' | 'month';
/** `cal.view`: the calendar by year (default) or Sundays per month (Plan 12, `pf.months-in-row`). */
const calViewCodec = enumCodec<CalView>(['year', 'month']);

function AttendanceCalendar({ shooterId }: { shooterId: number }) {
  const query = useShooterRounds(shooterId);
  // Plan 17: special shoots count as Sundays shot (an error leaves them out rather than blocking).
  const specials = useShooterSpecials(shooterId);
  const specialDates = useMemo(
    () => (specials.data ?? []).map((s) => s.event_date),
    [specials.data],
  );
  // `calYear`, not `cal`: the ChartFrame below keeps its Table/Fullscreen view state under urlKey "cal" (C10).
  const [yearParam, setYear] = useUrlState('calYear', intCodec, 0);
  const { range } = useTimeWindow();
  const pending = useWindowPending();
  const [view, setView] = useUrlState<CalView>('cal.view', calViewCodec, 'year');
  // An insight link's dates win over the time window: the calendar opens on the year they end in.
  const shown = useTargetWindow('cal', range);
  // The month view opens on the whole year the window ends in (All time: every month).
  const monthsWindow = yearOf(shown);
  const viewChips = (
    <div role="group" aria-label="Calendar view" className="flex flex-wrap gap-2">
      <Chip selected={view === 'year'} onClick={() => setView('year')}>
        By year
      </Chip>
      <Chip selected={view === 'month'} onClick={() => setView('month')}>
        By month
      </Chip>
    </div>
  );
  return (
    <QueryChart
      title="Attendance calendar"
      query={query}
      waiting={pending || specials.isPending}
      isEmpty={(d) => d.length === 0 && specialDates.length === 0}
      emptyText="No Sundays shot yet"
      controls={viewChips}
    >
      {(rounds) => {
        if (view === 'month') {
          const m = monthsModel(rounds, specialDates);
          return (
            <ChartFrame
              title="Sundays shot per month"
              subtitle="Every month from your first round to your latest"
              option={m.option}
              window={monthsWindow}
              columns={m.columns}
              rows={m.rows}
              csvName={`attendance-months-${shooterId}`}
              ariaLabel="Sundays shot per month"
              urlKey="cal"
              controls={viewChips}
              explainer={explainers['cal-month']}
            />
          );
        }
        const years = activeYears(rounds, specialDates);
        // Opens on the year the window ends in (or the latest year they shot up to it).
        const endYear = shown === null ? Infinity : Number(shown.to.slice(0, 4));
        const opening = years.find((y) => y <= endYear) ?? (years[0] as number);
        const year = years.includes(yearParam) ? yearParam : opening;
        const yearChips = (
          <div className="flex flex-col gap-2">
            {viewChips}
            <div role="group" aria-label="Calendar year" className="flex flex-wrap gap-2">
              {years.map((y) => (
                <Chip key={y} selected={y === year} onClick={() => setYear(y)}>
                  {String(y)}
                </Chip>
              ))}
            </div>
          </div>
        );
        return (
          <AttendanceYear
            shooterId={shooterId}
            year={year}
            rounds={rounds}
            specialDates={specialDates}
            yearChips={yearChips}
          />
        );
      }}
    </QueryChart>
  );
}

/** How the day played, per Sunday, for every Sunday (joined to the shooter's rounds by date). */
const DIFFICULTY_BY_EVENT = querySpec({
  metric: 'difficulty',
  agg: 'avg',
  group_by: ['event'],
  limit: 5000,
});

const TOUGH_TITLE = 'Tough days';

function ToughDaysChart({ shooterId }: { shooterId: number }) {
  const rounds = useShooterRounds(shooterId);
  const difficulty = useExplore(DIFFICULTY_BY_EVENT);
  const { window: choice, range } = useTimeWindow();
  // An insight link's dates win over the time window (they span the whole career).
  const { target } = useChartTarget('tough-days');
  const shown = target.window ?? range;
  const phrase = target.window === null ? windowPhrase(choice, range) : rangeText(target.window);
  return (
    <QueryChart
      title={TOUGH_TITLE}
      query={rounds}
      isEmpty={(d) => d.length === 0}
      emptyText="No rounds yet"
    >
      {(every) => (
        <QueryChart
          title={TOUGH_TITLE}
          query={difficulty}
          isEmpty={({ result }) => toughDaysModel(every, result.rows).rows.length === 0}
          emptyText="No Sundays with field results yet"
        >
          {({ result }) => {
            const all = toughDaysModel(every, result.rows);
            // The card shows the time window; fullscreen and the CSV keep every Sunday.
            const mine = shown === null ? every : filterRowsByWindow(every, 'event_date', shown);
            const m = toughDaysModel(mine, result.rows);
            if (m.rows.length === 0) {
              return (
                <Card title={TOUGH_TITLE}>
                  <EmptyState
                    title={`No Sundays with field results in ${phrase}`}
                    description="Pick 12M or All in the time filter above to see more."
                  />
                </Card>
              );
            }
            const full: ChartFull = {
              option: all.option,
              rows: all.rows,
              note: 'Every Sunday you shot with field results. The card shows the time window.',
            };
            return (
              <ChartFrame
                title={TOUGH_TITLE}
                subtitle={`Against the field by how hard the Sunday played, ${phrase}`}
                option={m.option}
                columns={m.columns}
                rows={m.rows}
                full={full}
                csvName={`tough-days-${shooterId}`}
                ariaLabel="Against the field by how hard each Sunday played"
                urlKey="tough-days"
                rowHref={eventHref('event_date')}
                rowHrefKey="event_date"
                explainer={explainers['tough-days']}
              />
            );
          }}
        </QueryChart>
      )}
    </QueryChart>
  );
}

export function ProfileCharts({ shooterId }: { shooterId: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="min-w-0">
        <RatingChart shooterId={shooterId} />
      </div>
      <div className="min-w-0">
        <TrendChart shooterId={shooterId} />
      </div>
      <div className="min-w-0">
        <FinishesChart shooterId={shooterId} />
      </div>
      <div className="min-w-0">
        <DistributionChart shooterId={shooterId} />
      </div>
      <div className="min-w-0">
        <LearningCurveChart shooterId={shooterId} />
      </div>
      <div className="min-w-0">
        <SplitsChart shooterId={shooterId} />
      </div>
      <div className="min-w-0">
        <ToughDaysChart shooterId={shooterId} />
      </div>
      <div className="min-w-0">
        <AttendanceCalendar shooterId={shooterId} />
      </div>
    </div>
  );
}
