import type { ReactNode } from 'react';
import { Card } from '../../../components/ui/Card';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useShooterInsights } from '../api';
import type { ShooterInsights } from '../api';
import { explainers } from '../explainers';
import {
  formatDay,
  formatPct,
  formatSigned,
  formLabel,
  MIN_FLOOR_ROUNDS,
  MIN_RUST_ROUNDS,
  NOT_ENOUGH,
  plural,
} from '../format';
import { InfoItem } from './InfoItem';
import { AllRoundTypesTag } from './InlineExplainer';

export function rustText(rust: ShooterInsights['rust']): string {
  if (rust.n === 0) return 'No 3-week breaks yet';
  if (rust.effect === null || rust.n < MIN_RUST_ROUNDS) {
    return `${NOT_ENOUGH} (${plural(rust.n, 'round')} after a break)`;
  }
  return `${formatSigned(rust.effect)} after 3+ weeks off (${plural(rust.n, 'round')}; club ${formatSigned(rust.club_effect)})`;
}

/** Plan 06 T8 milestone: the next C12 tier; `next_events` is null once 250 Sundays are passed. */
export function milestoneText(m: ShooterInsights['milestone']): string {
  if (m.next_events === null || m.events_to_go === null) return 'All milestones reached';
  const base = `${plural(m.next_events, 'Sunday')} — ${m.events_to_go} to go`;
  return m.projected_date === null ? base : `${base}, projected ${formatDay(m.projected_date)}`;
}

/** Long text values span both columns of the phone grid; from lg every item takes one of four columns. */
const WIDE = 'col-span-2 lg:col-span-1';

function InsightsGrid({ insights: i, deceased }: { insights: ShooterInsights; deceased: boolean }) {
  return (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <InfoItem
        label="Low end / High end"
        value={
          i.floor === null || i.ceiling === null
            ? '—'
            : i.recent_n < MIN_FLOOR_ROUNDS
              ? NOT_ENOUGH
              : `${i.floor.toFixed(1)} / ${i.ceiling.toFixed(1)}`
        }
        hint="Low and high end of your last 20 rounds"
        explainer={explainers['floor-ceiling']}
      />
      <InfoItem
        label="Bad-day rate"
        value={formatPct(i.bad_day_rate)}
        hint="Rounds 6+ targets under your expected score"
        explainer={explainers['bad-day']}
      />
      <InfoItem
        label="Form"
        value={i.form === null ? '—' : `${formLabel(i.form)} (${formatSigned(i.form)})`}
        hint="Vs your expected score, last 5 rounds"
        explainer={explainers.form}
      />
      <InfoItem
        label="Wins / podiums"
        value={`${i.wins} / ${i.podiums}`}
        explainer={explainers.wins}
      />
      <InfoItem
        label="Field beaten (avg)"
        value={formatPct(i.avg_percentile)}
        hint="Share of the other shooters you beat, on average"
        explainer={explainers['field-beaten']}
      />
      <InfoItem
        label="Peak rating"
        value={i.peak_mu === null ? '—' : i.peak_mu.toFixed(1)}
        hint={i.peak_date === null ? undefined : `Reached ${formatDay(i.peak_date)}`}
        explainer={explainers.peak}
      />
      <InfoItem
        label="Rust"
        value={rustText(i.rust)}
        hint="First Sunday back vs your other rounds"
        className={WIDE}
        explainer={explainers.rust}
      />
      {/* A memorial profile projects no future events. */}
      {!deceased && (
        <InfoItem
          label="Next milestone"
          value={milestoneText(i.milestone)}
          className={WIDE}
          explainer={explainers.milestone}
        />
      )}
    </dl>
  );
}

export function InsightsCard({
  shooterId,
  deceased = false,
}: {
  shooterId: number;
  deceased?: boolean;
}) {
  const insights = useShooterInsights(shooterId);
  let body: ReactNode;
  if (insights.isPending) body = <Skeleton className="h-32" />;
  else if (insights.isError)
    body = <p className="text-text-muted">Insights unavailable right now.</p>;
  else body = <InsightsGrid insights={insights.data} deceased={deceased} />;
  return (
    <Card
      title="Stats"
      subtitle={
        insights.data === undefined
          ? undefined
          : `As of ${formatDay(insights.data.as_of)} · not affected by the time filter`
      }
      actions={<AllRoundTypesTag />}
    >
      {body}
    </Card>
  );
}
