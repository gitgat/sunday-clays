import { ChartFrame } from '../../components/charts/ChartFrame';
import { AboutBlock } from '../../components/ui/AboutBlock';
import type { TabularData, TabularRow } from '../../components/charts/types';
import { formatDate } from '../../lib/format';
import { useShooterAchievements } from './api';
import { explainers } from './explainers';
import { cumulativeByDate, cumulativeLineOption } from './chartOptions';
import { ProgressBar } from './components/ProgressBar';
import { TrophyIcon } from './components/TrophyIcon';
import { formatCount, trophyTitle } from './labels';

const TIMELINE_COLUMNS: TabularData['columns'] = [
  { key: 'date', label: 'Date', type: 'date' },
  { key: 'trophy', label: 'Trophy', type: 'string' },
];

/** An insight's trophy codes as the dates that trophy was earned (the timeline's x values). */
export function trophyDates(keys: readonly string[], rows: readonly TabularRow[]): string[] {
  return rows.filter((r) => keys.includes(String(r.code))).map((r) => String(r.date));
}

export function TrophyCase({ shooterId }: { shooterId: number }) {
  const { data, isPending, isError } = useShooterAchievements(shooterId);
  if (isPending) return <p role="status">Loading trophies…</p>;
  if (isError) return <p role="alert">Could not load the trophies for this shooter.</p>;
  // `code` is not a column: it lets an insight's trophy code find its points (Plan 12 hlLabels).
  const timeline = data.earned
    .flatMap((earned) =>
      earned.dates.map((date) => ({ date, trophy: trophyTitle(earned), code: earned.code })),
    )
    .sort((a, b) => a.date.localeCompare(b.date));
  const points = cumulativeByDate(timeline.map((row) => row.date));
  return (
    <section aria-label="Trophy case for this shooter" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-medium">Earned trophies</h3>
        <span className="rounded-button border border-outline-variant px-2 py-0.5 text-xs text-text-muted">
          Lifetime
        </span>
      </div>
      {data.earned.length === 0 ? (
        <p className="text-text-muted">No trophies yet — they come from showing up and shooting.</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.earned.map((earned) => (
            <li
              key={earned.code}
              className="flex min-h-11 items-center gap-3 rounded-xl bg-elevated p-3"
            >
              <TrophyIcon artKey={earned.art_key} metal={earned.metal} locked={false} size={48} />
              <span className="flex flex-col">
                <span className="font-medium">
                  {earned.count > 1 ? `${earned.name} ×${earned.count}` : earned.name}
                </span>
                {earned.label === null ? null : (
                  <span className="text-sm text-text-muted">{earned.label}</span>
                )}
                <time className="text-xs text-text-muted" dateTime={earned.first_date}>
                  {formatDate(earned.first_date)}
                </time>
              </span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="text-lg font-medium">Next tiers</h3>
      <AboutBlock explainer={explainers['trophy-progress']} label="About next tiers" />
      <ul className="flex flex-col gap-3">
        {data.progress.map((p) => (
          <li key={p.code} className="flex items-center gap-3">
            <TrophyIcon
              artKey={p.art_key}
              metal={p.next_metal ?? p.earned_metal}
              locked={p.next_level !== null}
              size={40}
            />
            <span className="flex flex-1 flex-col gap-1">
              <span className="font-medium">{p.name}</span>
              {p.next_threshold === null ? (
                <span className="text-sm text-accent">All tiers earned</span>
              ) : (
                <>
                  <ProgressBar
                    value={p.value}
                    max={p.next_threshold}
                    label={`${p.name} progress`}
                  />
                  <span className="text-sm text-text-muted">
                    {formatCount(p.value)} / {p.next_label}
                  </span>
                </>
              )}
            </span>
          </li>
        ))}
      </ul>
      {data.locked.length > 0 ? (
        <>
          <h3 className="text-lg font-medium">Locked</h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {data.locked.map((locked) => (
              <li key={locked.code} className="flex min-h-11 items-center gap-3">
                <TrophyIcon artKey={locked.art_key} metal={null} locked size={32} />
                <span className="flex flex-col">
                  <span>{locked.name}</span>
                  <span className="text-xs text-text-muted">{locked.description}</span>
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {timeline.length > 0 ? (
        <ChartFrame
          title="Trophy timeline"
          subtitle="Trophies earned over time · all years"
          option={cumulativeLineOption(points, 'Trophies')}
          columns={TIMELINE_COLUMNS}
          rows={timeline}
          csvName={`trophies-${shooterId}`}
          ariaLabel="Line chart of trophies earned over time"
          urlKey="trophytl"
          zoom="x"
          explainer={explainers.trophytl}
          hlLabels={trophyDates}
        />
      ) : null}
    </section>
  );
}
