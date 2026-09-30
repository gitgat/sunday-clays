import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { useShooterRounds } from '../api';
import type { PersonalBest } from '../api';
import { roundsBefore } from '../charts';
import { explainers } from '../explainers';
import { formatDay, MIN_PB_EARLIER_ROUNDS } from '../format';
import { InlineExplainer } from './InlineExplainer';

/** A visible, 44 px link to the event that keeps the global round-type filter (C10). */
function EventLink({ date }: { date: string }) {
  return (
    <Link
      to={useRoundTypeLink(`/events/${date}`)}
      className="inline-flex min-h-11 min-w-11 items-center underline underline-offset-2"
    >
      {formatDay(date)}
    </Link>
  );
}

/** Overall first, then calendar years newest first (Plan 06 PbOut scopes 'overall' and 'year'). */
function pbOrder(a: PersonalBest, b: PersonalBest): number {
  if (a.scope !== b.scope) return a.scope === 'overall' ? -1 : 1;
  return b.key.localeCompare(a.key);
}

export function PbTable({ shooterId, pbs }: { shooterId: number; pbs: PersonalBest[] }) {
  const sorted = [...pbs].sort(pbOrder);
  // The same filtered rounds the personal bests were picked from; until they load nothing is marked.
  const rounds = useShooterRounds(shooterId).data;
  const isEarly = (pb: PersonalBest) =>
    rounds !== undefined && roundsBefore(rounds, pb.event_date) < MIN_PB_EARLIER_ROUNDS;
  return (
    <Card title="Personal bests">
      {sorted.length === 0 ? (
        <p className="text-text-muted">No personal bests yet</p>
      ) : (
        <div className="flex flex-col gap-2">
          <InlineExplainer label="About personal bests" explainer={explainers.pbs} />
          <div className="overflow-x-auto">
            <table aria-label="Personal bests" className="w-full text-sm">
              <thead className="text-left text-text-muted">
                <tr>
                  <th scope="col" className="py-2 pr-2">
                    Best of
                  </th>
                  <th scope="col" className="py-2 pr-2 text-right">
                    Score
                  </th>
                  <th scope="col" className="py-2">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((pb) => (
                  <tr key={`${pb.scope}-${pb.key}`} className="border-t border-outline-variant">
                    <td className="py-2 pr-2">{pb.scope === 'overall' ? 'Overall' : pb.key}</td>
                    <td className="py-2 pr-2 text-right tabular-nums">
                      {pb.score}
                      {isEarly(pb) && (
                        <span className="ml-1 text-xs text-text-muted">
                          <span aria-hidden="true">(early)</span>
                          <span className="sr-only"> early, from your first 5 rounds</span>
                        </span>
                      )}
                    </td>
                    <td className="py-2">
                      <EventLink date={pb.event_date} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-muted">
            {rounds !== undefined &&
              '“early” = a best from your first 5 rounds, so it does not count as a new personal best. '}
            Personal bests by time of year, month, round type, gauge and weather are the Best column
            of the Splits chart’s table.
          </p>
        </div>
      )}
    </Card>
  );
}
