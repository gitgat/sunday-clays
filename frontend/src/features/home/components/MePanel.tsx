import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { ApiError } from '../../../api/errors';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { clearMe } from '../../../lib/me';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { About } from '../../events/components/About';
import { useShooterDetail, useShooterRounds } from '../api';
import type { ShooterDetail, ShooterRound } from '../api';
import { homeExplainers } from '../explainers';
import { formatDay, formatSigned, ordinal, round1 } from '../format';
import type { HomeWidget } from '../widgets';
import { WidgetSlot } from './WidgetSlot';

export type LastResult = {
  date: string;
  score: number;
  rank: number | null;
  ratingMove: number | null;
};

/** The best round on the latest attended date (the top score when metrics are not computed yet). */
export function lastResult(rounds: ShooterRound[]): LastResult | null {
  if (rounds.length === 0) return null;
  const date = rounds.reduce((latest, r) => (r.event_date > latest ? r.event_date : latest), '');
  const day = rounds.filter((r) => r.event_date === date);
  const best =
    day.find((r) => r.is_best_round) ?? day.reduce((a, b) => (b.score > a.score ? b : a));
  // A partial-results Sunday is not rated (ratings do not move): its rounds carry no field median,
  // so that is the signal for a dash rather than a 0.0.
  const ratingMove =
    best.field_median === null || best.mu_before === null || best.mu_after === null
      ? null
      : round1(best.mu_after - best.mu_before);
  return { date, score: best.score, rank: best.event_rank, ratingMove };
}

function LastResultView({ result }: { result: LastResult }) {
  const eventLink = useRoundTypeLink(`/events/${result.date}`);
  return (
    // Every value sits in a 44px row, so the date link is a full tap target (C10) and the three
    // values stay on one line.
    <dl className="grid grid-cols-3 gap-2">
      <div>
        <dt className="text-xs text-text-muted">Last out</dt>
        <dd className="flex min-h-11 items-center">
          <Link to={eventLink} className="inline-flex min-h-11 items-center underline">
            {formatDay(result.date)}
          </Link>
        </dd>
      </div>
      <div>
        <dt className="text-xs text-text-muted">Score · finish</dt>
        <dd className="flex min-h-11 items-center tabular-nums">{`${result.score} · ${result.rank === null ? '—' : ordinal(result.rank)}`}</dd>
      </div>
      <div>
        <dt className="text-xs text-text-muted">Rating move</dt>
        <dd className="flex min-h-11 items-center tabular-nums">
          {formatSigned(result.ratingMove)}
        </dd>
      </div>
    </dl>
  );
}

function MeOdometer({ odometer }: { odometer: ShooterDetail['odometer'] }) {
  const items = [
    ['Clays broken', odometer.clays_broken],
    ['Sundays', odometer.events],
    ['Current streak', odometer.current_streak],
  ] as const;
  return (
    <div>
      <About explainer={homeExplainers.meOdometer} label="About your totals" />
      <ul aria-label="Your odometer" className="grid grid-cols-3 gap-2">
        {items.map(([label, value]) => (
          <li key={label} className="flex flex-col">
            <span className="text-xs text-text-muted">{label}</span>
            <span className="tabular-nums">{value.toLocaleString('en-US')}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MeDetails({
  meId,
  onCleared,
  widgets,
}: {
  meId: number;
  onCleared: () => void;
  widgets: HomeWidget[];
}) {
  const detail = useShooterDetail(meId);
  const rounds = useShooterRounds(meId);
  const profileLink = useRoundTypeLink(`/shooters/${meId}`);

  if (detail.isPending) return <Skeleton className="h-40" />;
  if (detail.isError) {
    if (detail.error instanceof ApiError && detail.error.status === 404) {
      return (
        <div className="flex flex-col gap-3">
          <p>We couldn’t find your shooter profile — it may have been merged into another name.</p>
          <Button
            className="self-start"
            onClick={() => {
              clearMe();
              onCleared();
            }}
          >
            Choose again
          </Button>
        </div>
      );
    }
    return <EmptyState title="Couldn't load your panel" description={detail.error.message} />;
  }

  let result: ReactNode;
  if (rounds.isPending) result = <Skeleton className="h-12" />;
  else if (rounds.isError) result = <p className="text-text-muted">Last result unavailable.</p>;
  else {
    const last = lastResult(rounds.data);
    result =
      last === null ? (
        <p className="text-text-muted">No rounds yet.</p>
      ) : (
        <div>
          <About explainer={homeExplainers.meLast} label="About your last Sunday" />
          <LastResultView result={last} />
        </div>
      );
  }

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-lg font-medium">
        <Link to={profileLink} className="inline-flex min-h-11 min-w-11 items-center">
          {detail.data.display_name}
        </Link>
      </h3>
      {result}
      <MeOdometer odometer={detail.data.odometer} />
      <WidgetSlot slot="me" widgets={widgets} meId={meId} />
    </div>
  );
}

export function MePanel({
  meId,
  onCleared,
  widgets,
}: {
  meId: number | null;
  onCleared: () => void;
  widgets: HomeWidget[];
}) {
  const shootersLink = useRoundTypeLink('/shooters');
  return (
    <Card title="Your panel">
      {meId === null ? (
        // The link stands on its own line: inline in the sentence it could not be 44px tall (C10).
        <div className="flex flex-col gap-2">
          <p>
            Find yourself in Shooters and tap “That’s me” to see your last result, rating move and
            odometer here.
          </p>
          <Link
            to={shootersLink}
            className="inline-flex min-h-11 items-center self-start underline"
          >
            Go to Shooters
          </Link>
        </div>
      ) : (
        <MeDetails meId={meId} onCleared={onCleared} widgets={widgets} />
      )}
    </Card>
  );
}
