import type { ECElementEvent } from 'echarts';
import { useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router';

import { barOption } from '../../../components/charts/builders/bar';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import {
  rowTargeted,
  shooterLabels,
  useChartTarget,
  useScrollToTarget,
} from '../../../components/charts/chartTarget';
import type { ChartFull, Explainer, TabularData } from '../../../components/charts/types';
import { AboutBlock } from '../../../components/ui/AboutBlock';
import { Card } from '../../../components/ui/Card';
import { useRoundTypeHref, useRoundTypes } from '../../../lib/roundTypes';
import { recordsExplainer, type RecordsRange } from '../explainers';
import {
  expandedLimit,
  fetchAllRecords,
  RECORDS_MAX_ROWS,
  useAllRecords,
  type RecordJumpOut,
  type RecordRatingOut,
  type RecordRoundOut,
  type RecordShooterOut,
  type RecordsOut,
} from '../api';
import { chartRows, formatEventDate, formatRating, formatSigned, labelIds } from '../format';

const hlLabels = shooterLabels('display_name');

function NoneYet() {
  return <p className="text-sm text-text-muted">None yet</p>;
}

const LINK = 'inline-flex min-h-11 min-w-11 items-center underline underline-offset-2';

/**
 * Shooter and event links keep the global round-type filter (C10). A 44 px tap target (it sets the row height),
 * underlined without hover, and free to wrap so a long name never widens the page at 390 px.
 */
function ShooterLink({ id, name }: { id: number; name: string }) {
  const href = useRoundTypeHref();
  return (
    <Link to={href(`/shooters/${String(id)}`)} className={`${LINK} min-w-0 break-words`}>
      {name}
    </Link>
  );
}

function EventLink({ date }: { date: string }) {
  const href = useRoundTypeHref();
  return (
    <Link to={href(`/events/${date}`)} className={LINK}>
      {formatEventDate(date)}
    </Link>
  );
}

/** One ranked record, whichever list it comes from. */
interface RecordRow {
  shooterId: number;
  name: string;
  rank: number;
  value: string;
  /** The number behind `value`, for "N more tied at X". */
  raw: number;
  date: string;
}

/**
 * Round records carry no ordinal, and one shooter can hold two same-day rounds in a list (the fixture has 39 second
 * rounds), so the list position keeps the React key unique.
 */
function rowKey(index: number, row: RecordRow): string {
  return `${String(index)}-${String(row.shooterId)}-${row.date}`;
}

/** The dates a records list counts, and how to ask for its full list. */
export interface RecordsScope {
  since: string | null;
  asOf: string | null;
}

/** One list's size: every row that qualifies, and how many the ten-row cut leaves tied with the last one shown. */
export interface ListSize {
  total: number;
  tiedMore: number;
}

/** "Show all N" (lazy: the full list is fetched when it is first asked for) under a list of ten rows. */
function useShowAll(
  rows: readonly RecordRow[],
  size: ListSize,
  scope: RecordsScope,
  pick: (all: RecordsOut) => readonly RecordRow[],
) {
  const [expanded, setExpanded] = useState(false);
  const limit = expandedLimit(size.total);
  const all = useAllRecords(scope, limit, expanded);
  const full = expanded && all.data !== undefined ? pick(all.data) : null;
  return {
    shown: full ?? rows,
    open: full !== null,
    loading: expanded && all.isPending,
    failed: expanded && all.isError,
    capped: full !== null && size.total > RECORDS_MAX_ROWS,
    expand: () => {
      // A retry after a failed fetch asks again.
      if (expanded) void all.refetch();
      else setExpanded(true);
    },
    collapse: () => {
      setExpanded(false);
    },
  };
}

const MORE_BUTTON =
  'inline-flex min-h-11 items-center rounded-button px-2 text-accent underline underline-offset-2 disabled:opacity-60';

/** The tie note, "Show all N" and its loading, error and "top 500" messages under a list. */
function ListFooter({
  size,
  shownCount,
  formatTie,
  lastRaw,
  more,
}: {
  size: ListSize;
  shownCount: number;
  formatTie: (raw: number) => string;
  lastRaw: number | undefined;
  more: ReturnType<typeof useShowAll>;
}) {
  if (size.total <= shownCount && !more.open) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-3 pt-2 text-sm text-text-muted">
      {!more.open && size.tiedMore > 0 && lastRaw !== undefined && (
        <span>
          {String(size.tiedMore)} more tied at {formatTie(lastRaw)}
        </span>
      )}
      {more.open ? (
        <>
          {more.capped && (
            <span>
              Showing the top {String(RECORDS_MAX_ROWS)} of {String(size.total)}.
            </span>
          )}
          <button type="button" onClick={more.collapse} className={MORE_BUTTON}>
            Show fewer
          </button>
        </>
      ) : (
        <button type="button" onClick={more.expand} disabled={more.loading} className={MORE_BUTTON}>
          {more.loading
            ? 'Loading…'
            : size.total > RECORDS_MAX_ROWS
              ? `Show top ${String(RECORDS_MAX_ROWS)} of ${String(size.total)}`
              : `Show all ${String(size.total)}`}
        </button>
      )}
      {more.failed && <span role="alert">Could not load the full list. Try again.</span>}
    </div>
  );
}

function RecordTable({
  title,
  subtitle,
  valueLabel,
  rows,
  size,
  scope,
  pick,
  formatTie,
  expandable = true,
  urlKey,
  explainer,
}: {
  /** False keeps the list a fixed top ten: no "Show all" and no tie note (Highest ratings). */
  expandable?: boolean;
  title: string;
  subtitle: string;
  valueLabel: string;
  rows: readonly RecordRow[];
  size: ListSize;
  scope: RecordsScope;
  pick: (all: RecordsOut) => readonly RecordRow[];
  formatTie: (raw: number) => string;
  /** Makes the table an insight target: `#chart-{urlKey}` and rows ringed by `{urlKey}.hl`. */
  urlKey?: string;
  /** "About this table" under the list. */
  explainer?: Explainer;
}) {
  const more = useShowAll(rows, size, scope, pick);
  const { target } = useChartTarget(urlKey ?? '');
  useScrollToTarget(urlKey ?? '', urlKey !== undefined);
  const hl = urlKey === undefined ? [] : target.hl;
  return (
    <Card
      title={title}
      subtitle={subtitle}
      className="min-w-0"
      id={urlKey === undefined ? undefined : `chart-${urlKey}`}
    >
      {rows.length === 0 ? (
        <NoneYet />
      ) : (
        <>
          <table aria-label={title} className="w-full text-left text-sm">
            <thead className="text-text-muted">
              <tr>
                <th scope="col" className="py-2 pr-2">
                  #
                </th>
                <th scope="col" className="py-2 pr-2">
                  Shooter
                </th>
                <th scope="col" className="py-2 pr-2 text-right">
                  {valueLabel}
                </th>
                <th scope="col" className="py-2 text-right">
                  Date
                </th>
              </tr>
            </thead>
            <tbody>
              {more.shown.map((row, i) => (
                <tr
                  key={rowKey(i, row)}
                  aria-current={rowTargeted(hl, row.shooterId, row.date) ? 'true' : undefined}
                  className={
                    rowTargeted(hl, row.shooterId, row.date)
                      ? 'border-t border-outline-variant bg-accent/15 font-medium'
                      : 'border-t border-outline-variant'
                  }
                >
                  <td className="py-2 pr-2 tabular-nums">{row.rank}</td>
                  <td className="min-w-0 pr-2">
                    <ShooterLink id={row.shooterId} name={row.name} />
                  </td>
                  <td className="py-2 pr-2 text-right tabular-nums">{row.value}</td>
                  <td className="text-right">
                    <EventLink date={row.date} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {expandable && (
            <ListFooter
              size={size}
              shownCount={rows.length}
              formatTie={formatTie}
              lastRaw={rows.at(-1)?.raw}
              more={more}
            />
          )}
          <AboutBlock explainer={explainer} />
        </>
      )}
    </Card>
  );
}

function roundRows(
  rows: readonly RecordRoundOut[],
  format: (value: number) => string,
): RecordRow[] {
  return rows.map((row) => ({
    shooterId: row.shooter_id,
    name: row.display_name,
    rank: row.rank,
    value: format(row.value),
    raw: row.value,
    date: row.event_date,
  }));
}

function jumpRows(rows: readonly RecordJumpOut[]): RecordRow[] {
  return rows.map((row) => ({
    shooterId: row.shooter_id,
    name: row.display_name,
    rank: row.rank,
    value: `${String(row.from_score)} → ${String(row.to_score)} (+${String(row.value)})`,
    raw: row.value,
    date: row.event_date,
  }));
}

/** What every list needs: the period tag for its subtitle, its size, and the dates for "Show all". */
export interface ListProps {
  /** "Last 8 weeks · Aug 3 – Sep 27": every card's subtitle starts with it. */
  period: string;
  size: ListSize;
  scope: RecordsScope;
}

export function HighestScores({
  rows,
  period,
  size,
  scope,
  range,
}: { rows: readonly RecordRoundOut[]; range: RecordsRange } & ListProps) {
  return (
    <RecordTable
      title="Highest scores"
      subtitle={`${period} · Single rounds, best first. Ties share a place.`}
      valueLabel="Score"
      rows={roundRows(rows, (value) => String(value))}
      size={size}
      scope={scope}
      pick={(all) => roundRows(all.highest_scores, (value) => String(value))}
      formatTie={String}
      urlKey="rec-highest"
      explainer={recordsExplainer('rec-highest', range)}
    />
  );
}

export function BiggestAdjusted({
  rows,
  period,
  size,
  scope,
}: { rows: readonly RecordRoundOut[] } & ListProps) {
  return (
    <RecordTable
      title="Biggest day vs the field"
      subtitle={`${period} · Round score minus that Sunday’s middle score, on Sundays with complete results.`}
      valueLabel="Above middle score"
      rows={roundRows(rows, formatSigned)}
      size={size}
      scope={scope}
      pick={(all) => roundRows(all.biggest_adjusted, formatSigned)}
      formatTie={formatSigned}
    />
  );
}

export function BiggestJumps({
  rows,
  period,
  size,
  scope,
}: { rows: readonly RecordJumpOut[] } & ListProps) {
  return (
    <RecordTable
      title="Biggest jump from one Sunday to the next"
      subtitle={`${period} · Best round on one Sunday to the best round on the next Sunday shot. The date is the later Sunday. Both Sundays of a jump must be inside these dates.`}
      valueLabel="Jump"
      rows={jumpRows(rows)}
      size={size}
      scope={scope}
      pick={(all) => jumpRows(all.biggest_jumps)}
      formatTie={(raw) => `+${String(raw)}`}
    />
  );
}

export function HighestRatings({
  rows,
  period,
  size,
  scope,
}: { rows: readonly RecordRatingOut[] } & ListProps) {
  return (
    <RecordTable
      title="Highest rating in these dates"
      subtitle={`${period} · All round types · needs 5 or more rounds. Peaks on Sundays inside these dates; the 5-round rule still counts every round shot before them.`}
      valueLabel="Rating"
      rows={roundRows(rows, formatRating)}
      size={size}
      scope={scope}
      pick={(all) => roundRows(all.highest_ratings, formatRating)}
      formatTie={formatRating}
      expandable={false}
    />
  );
}

export function PerfectRounds({
  rows,
  period,
  size,
  scope,
}: { rows: readonly RecordRoundOut[] } & ListProps) {
  const more = useShowAll(roundRows(rows, String), size, scope, (all) =>
    roundRows(all.perfect_rounds, String),
  );
  const cut = size.total > rows.length;
  const subtitle = `${period} · Every 50 out of 50, newest first${cut && !more.open ? `. The latest ${String(rows.length)} of ${String(size.total)}.` : '.'}`;
  return (
    <Card title="Perfect 50s" subtitle={subtitle} className="min-w-0">
      {rows.length === 0 ? (
        <NoneYet />
      ) : (
        <>
          <ul className="flex flex-col">
            {more.shown.map((row, i) => (
              <li
                key={`${String(i)}-${String(row.shooterId)}-${row.date}`}
                className="flex flex-wrap items-center justify-between gap-x-2 border-t border-outline-variant first:border-t-0"
              >
                <ShooterLink id={row.shooterId} name={row.name} />
                <EventLink date={row.date} />
              </li>
            ))}
          </ul>
          <ListFooter
            size={{ total: size.total, tiedMore: 0 }}
            shownCount={rows.length}
            formatTie={String}
            lastRaw={undefined}
            more={more}
          />
        </>
      )}
    </Card>
  );
}

/** The bar chart, its table and the ids that link a bar to its shooter, for one list of shooters. */
function shooterModel(rows: readonly RecordShooterOut[], valueLabel: string) {
  const data: TabularData = {
    columns: [
      { key: 'display_name', label: 'Shooter', type: 'string' },
      { key: 'value', label: valueLabel, type: 'int' },
    ],
    rows: chartRows(rows),
  };
  return {
    data,
    option: barOption(data, { x: 'display_name', y: ['value'], horizontal: true }),
    ids: labelIds(rows),
  };
}

const chartHeight = (n: number) => Math.max(240, 80 + 28 * n);

/**
 * A top-10 bar chart of shooters in ChartFrame (C10); a bar or a table row opens that shooter. Fullscreen and
 * the CSV list every shooter on that list (`field`), fetched when fullscreen opens or CSV is pressed.
 */
export function ShooterRecordChart({
  title,
  valueLabel,
  rows,
  urlKey,
  field,
  range,
  period,
  size,
  scope,
}: {
  title: string;
  valueLabel: string;
  rows: readonly RecordShooterOut[];
  urlKey: string;
  field: 'most_events' | 'longest_streaks';
  range: RecordsRange;
} & ListProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const href = useRoundTypeHref();
  const [roundTypes] = useRoundTypes();
  const model = useMemo(() => shooterModel(rows, valueLabel), [rows, valueLabel]);
  const { since, asOf } = scope;
  const limit = expandedLimit(size.total);
  const fullQuery = useMemo(
    () => ({
      // The page's own key is ['/api/records', query]; 'chart-full' keeps this one apart from it.
      queryKey: ['/api/records', { roundTypes, since, asOf }, 'chart-full', field, limit],
      queryFn: async (): Promise<ChartFull> => {
        const all = shooterModel(
          (await fetchAllRecords(roundTypes, since, asOf, limit))[field],
          valueLabel,
        );
        return {
          option: all.option,
          rows: all.data.rows,
          height: chartHeight(all.data.rows.length),
          note: 'Every shooter.',
          // The full list covers the same window as the card, so the tag keeps naming it.
          scope: 'windowed',
        };
      },
    }),
    [roundTypes, since, asOf, field, valueLabel, limit],
  );

  if (rows.length === 0) {
    return (
      <Card title={title} subtitle={period} className="min-w-0">
        <NoneYet />
      </Card>
    );
  }
  return (
    <div className="min-w-0">
      <ChartFrame
        title={title}
        subtitle={`Top ${String(rows.length)}${size.total > rows.length ? ` of ${String(size.total)}` : ''}${size.tiedMore > 0 ? ` · ${String(size.tiedMore)} more tied at ${String((rows.at(-1) as RecordShooterOut).value)}` : ''}`}
        option={model.option}
        columns={model.data.columns}
        rows={model.data.rows}
        fullQuery={fullQuery}
        csvName={`records-${urlKey}`}
        ariaLabel={`${title} bar chart`}
        urlKey={urlKey}
        explainer={recordsExplainer(urlKey, range)}
        height={chartHeight(rows.length)}
        onEvents={{
          click: (params: ECElementEvent) => {
            // Fullscreen draws every shooter under labels of its own (namesakes get `#id`), so a bar the
            // top ten does not know is resolved from the fetched full rows.
            const id =
              model.ids.get(params.name) ??
              queryClient
                .getQueryData<ChartFull>(fullQuery.queryKey)
                ?.rows?.find((row) => row['display_name'] === params.name)?.['shooter_id'];
            if (typeof id === 'number') void navigate(href(`/shooters/${String(id)}`));
          },
        }}
        rowHref={(row) => `/shooters/${String(row['shooter_id'])}`}
        hlLabels={hlLabels}
      />
    </div>
  );
}
