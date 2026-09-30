import { useParams } from 'react-router';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { useYirShooter, type YirShooter } from '../api';
import { shooterMonthChart } from '../charts';
import { Stat } from '../components/Stat';
import { YirCard } from '../components/YirCard';
import { YirLink } from '../components/YirLink';
import { explainers } from '../explainers';
import { formatAvg, formatDay, formatInt, ordinal, versusGain } from '../format';

/** A rating that went up, "44.10 → 45.32"; a flat or lower rating shows a dash. */
function ratingGain(data: YirShooter): string {
  const { rating_start: start, rating_end: end } = data;
  if (start === null || end === null || end <= start) return '—';
  return `${formatAvg(start)} → ${formatAvg(end)}`;
}

function TheYear({ data }: { data: YirShooter }) {
  const { totals, previous } = data;
  const prevYear = data.year - 1;
  return (
    <YirCard title={`${data.display_name}: ${data.year}`} explainer={explainers.shooterYear}>
      <dl className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 md:grid-cols-3">
        <Stat
          label="Sundays"
          value={`${totals.events}${versusGain(totals.events, previous?.events ?? null, prevYear)}`}
        />
        <Stat
          label="Rounds"
          value={`${totals.rounds}${versusGain(totals.rounds, previous?.rounds ?? null, prevYear)}`}
        />
        <Stat label="Clays broken" value={formatInt(totals.clays_broken)} />
        <Stat
          label="Average score"
          value={`${formatAvg(totals.avg_score)}${versusGain(totals.avg_score, previous?.avg_score ?? null, prevYear, 2)}`}
        />
        <Stat
          label="Attendance"
          value={
            data.attendance_rank === null
              ? '—'
              : `${ordinal(data.attendance_rank)} of ${data.n_shooters}`
          }
        />
        <Stat label="Rating gain" value={ratingGain(data)} />
      </dl>
    </YirCard>
  );
}

function BestMoments({ data }: { data: YirShooter }) {
  return (
    <YirCard
      title={`${data.display_name}: best of ${data.year}`}
      explainer={explainers.shooterBest}
    >
      <dl className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Stat
          label="Best round"
          value={
            data.best === null ? '—' : `${data.best.score} on ${formatDay(data.best.event_date)}`
          }
        />
        <Stat label="Wins" value={String(data.wins)} />
        <Stat label="Podiums" value={String(data.podiums)} />
        <Stat
          label="Best finish"
          value={data.best_finish === null ? '—' : ordinal(data.best_finish)}
        />
        <Stat
          label="Personal bests"
          value={
            data.pbs.length === 0
              ? 'None this year'
              : data.pbs.map((p) => `${p.score} (${formatDay(p.event_date)})`).join(', ')
          }
        />
        <Stat label="Trophies earned" value={String(data.trophies)} />
      </dl>
    </YirCard>
  );
}

function ShooterYearView({ data }: { data: YirShooter }) {
  const chart = shooterMonthChart(data.months, data.display_name);
  return (
    <>
      <YirLink to={`/yir/${data.year}`}>Back to the club&apos;s {data.year}</YirLink>
      {data.totals.rounds === 0 ? <p>No rounds in {data.year}.</p> : null}
      <TheYear data={data} />
      <BestMoments data={data} />
      <ChartFrame
        title="Month by month"
        subtitle={`Average score per month against the club in ${data.year}`}
        option={chart.option}
        columns={chart.data.columns}
        rows={chart.data.rows}
        csvName={`yir-${data.year}-shooter-${data.shooter_id}-months`}
        ariaLabel={`${data.display_name}'s monthly average against the club in ${data.year}`}
        urlKey="ysm"
        zoom="none"
        explainer={explainers.shooterMonths}
      />
    </>
  );
}

export function YirShooterPage() {
  const params = useParams();
  const year = Number(params.year);
  const shooterId = Number(params.id);
  const query = useYirShooter(year, shooterId);
  return (
    <main className="mx-auto grid w-full min-w-0 max-w-5xl grid-cols-1 gap-4 p-4">
      <h1 className="text-2xl font-bold">Year in Review {year}</h1>
      {query.isPending ? (
        <p role="status">Loading Year in Review…</p>
      ) : query.isError ? (
        <p role="alert">{query.error.message}</p>
      ) : (
        <ShooterYearView data={query.data} />
      )}
    </main>
  );
}
