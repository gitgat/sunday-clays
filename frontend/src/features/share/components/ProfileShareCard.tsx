import type { ShooterDetail } from '../../shooters/api';
import { formatFullDay, formatInt } from '../format';

/** A lifetime odometer and personal best card for one shooter: only positive or neutral facts. */
export function ProfileShareCard({ shooter }: { shooter: ShooterDetail }) {
  const pb = shooter.pbs.find((p) => p.scope === 'overall');
  const odometer = shooter.odometer;
  return (
    <article className="flex flex-col gap-2 rounded-card bg-surface p-4 text-text">
      <p className="text-sm text-accent">Sunday Clays</p>
      <h3 className="break-words text-xl font-bold">{shooter.display_name}</h3>
      {shooter.deceased ? <p className="text-text-muted">In memory</p> : null}
      <dl className="grid grid-cols-2 gap-2">
        <dt className="text-text-muted">Personal best</dt>
        <dd>{pb === undefined ? '—' : `${pb.score} (${formatFullDay(pb.event_date)})`}</dd>
        <dt className="text-text-muted">Clays broken</dt>
        <dd>{formatInt(odometer.clays_broken)}</dd>
        <dt className="text-text-muted">Rounds</dt>
        <dd>{formatInt(odometer.rounds)}</dd>
        <dt className="text-text-muted">Sundays</dt>
        <dd>{formatInt(odometer.events)}</dd>
        <dt className="text-text-muted">Years active</dt>
        <dd>{odometer.years_active}</dd>
        <dt className="text-text-muted">Longest streak</dt>
        <dd>
          {odometer.longest_streak} {odometer.longest_streak === 1 ? 'Sunday' : 'Sundays'}
        </dd>
      </dl>
    </article>
  );
}
