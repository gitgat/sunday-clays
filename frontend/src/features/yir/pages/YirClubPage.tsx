import { useParams } from 'react-router';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { getMe } from '../../../lib/me';
import { useYirClub, type YirClub } from '../api';
import { clubMonthChart } from '../charts';
import { LeaderList } from '../components/LeaderList';
import { Stat } from '../components/Stat';
import { YirCard } from '../components/YirCard';
import { YirLink } from '../components/YirLink';
import { explainers } from '../explainers';
import { formatAvg, formatDay, formatInt, joinNames, versus } from '../format';

function AtAGlance({ data }: { data: YirClub }) {
  const { totals, previous } = data;
  const prevYear = data.year - 1;
  return (
    <YirCard title={`${data.year} at a glance`} explainer={explainers.glance}>
      <dl className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 md:grid-cols-3">
        <Stat
          label="Sundays with scores"
          value={`${totals.scored_events}${versus(totals.scored_events, previous?.scored_events ?? null, prevYear)}`}
        />
        <Stat
          label="Rounds"
          value={`${formatInt(totals.rounds)}${versus(totals.rounds, previous?.rounds ?? null, prevYear)}`}
        />
        <Stat
          label="Shooters"
          value={`${totals.shooters}${versus(totals.shooters, previous?.shooters ?? null, prevYear)}`}
        />
        <Stat label="Newcomers" value={String(data.newcomers)} />
        <Stat label="Clays broken" value={formatInt(totals.clays_broken)} />
        <Stat
          label="Average score"
          value={`${formatAvg(totals.avg_score)}${versus(totals.avg_score, previous?.avg_score ?? null, prevYear, 2)}`}
        />
      </dl>
    </YirCard>
  );
}

function Highlights({ data }: { data: YirClub }) {
  const top = data.top_rounds[0];
  return (
    <YirCard title={`${data.year} highlights`} explainer={explainers.highlights}>
      <dl className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Stat
          label="Top round"
          value={
            top === undefined
              ? '—'
              : `${top.score} by ${joinNames(data.top_rounds.map((r) => `${r.display_name} (${formatDay(r.event_date)})`))}`
          }
        />
        <Stat label="Perfect 50s" value={String(data.perfect_rounds)} />
        <Stat
          label="Busiest Sunday"
          value={
            data.busiest === null
              ? '—'
              : `${formatDay(data.busiest.event_date)} (${data.busiest.value} shooters)`
          }
        />
        <Stat
          label="Hardest Sunday"
          value={data.hardest === null ? '—' : formatDay(data.hardest.event_date)}
        />
        <Stat
          label="Easiest Sunday"
          value={data.easiest === null ? '—' : formatDay(data.easiest.event_date)}
        />
        <Stat label="Trophies earned" value={formatInt(data.trophies)} />
      </dl>
    </YirCard>
  );
}

function Leaders({ year, years }: { year: number; years: number[] }) {
  const currentYear = new Date().getFullYear();
  // Only the running year reads "to today"; a year with no scores has no board to show.
  if (year !== currentYear && !years.includes(year)) return null;
  const asOf = year === currentYear ? undefined : `${year}-12-31`;
  return (
    <YirCard title={`${year} leaders`} explainer={explainers.leaders}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <LeaderList title="Most Sundays" metric="events" asOf={asOf} year={year} />
        <LeaderList title="Best average" metric="avg_score" asOf={asOf} year={year} digits={2} />
        <LeaderList title="Most wins" metric="wins" asOf={asOf} year={year} />
        <LeaderList title="Points" metric="season_points" asOf={asOf} year={year} />
      </div>
    </YirCard>
  );
}

/** The year picker: the only date control on the page. */
function YearPicker({ data }: { data: YirClub }) {
  return (
    <nav aria-label="Other years" className="flex flex-wrap gap-2">
      {data.years.map((y) => (
        <YirLink
          key={y}
          to={`/yir/${y}`}
          aria-current={y === data.year ? 'page' : undefined}
          className={`justify-center rounded-button border px-3 no-underline ${
            y === data.year ? 'border-accent bg-elevated font-medium' : 'border-outline-variant'
          }`}
        >
          {y}
        </YirLink>
      ))}
    </nav>
  );
}

function ClubYearView({ data }: { data: YirClub }) {
  const chart = clubMonthChart(data.months);
  const me = getMe();
  return (
    <>
      <YearPicker data={data} />
      {me === null ? null : (
        <YirLink to={`/yir/${data.year}/shooters/${me}`}>Your {data.year}</YirLink>
      )}
      <AtAGlance data={data} />
      <Highlights data={data} />
      <Leaders year={data.year} years={data.years} />
      <ChartFrame
        title="Month by month"
        subtitle={`Rounds shot (bars) and the average score (line) in ${data.year}`}
        option={chart.option}
        columns={chart.data.columns}
        rows={chart.data.rows}
        csvName={`yir-${data.year}-months`}
        ariaLabel={`Rounds and average score per month in ${data.year}`}
        urlKey="ym"
        zoom="none"
        explainer={explainers.clubMonths}
      />
    </>
  );
}

export function YirClubPage() {
  const year = Number(useParams().year);
  const query = useYirClub(year);
  return (
    <main className="mx-auto grid w-full min-w-0 max-w-5xl grid-cols-1 gap-4 p-4">
      <h1 className="text-2xl font-bold">Year in Review {year}</h1>
      {query.isPending ? (
        <p role="status">Loading Year in Review…</p>
      ) : query.isError ? (
        <p role="alert">{query.error.message}</p>
      ) : (
        <ClubYearView data={query.data} />
      )}
    </main>
  );
}
