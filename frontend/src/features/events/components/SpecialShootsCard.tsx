import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import { useShooterSpecials } from '../../shooters/api';
import { eventExplainers } from '../explainers';
import { formatDay, specialName, specialTag } from '../format';
import { About } from './About';

/**
 * Plan 17 (Decision 19): the shooter's special shoots, newest first, each tagged "Special · 60" with
 * its score out of that total. Renders nothing for a shooter without one (or while it cannot load).
 */
export function SpecialShootsCard({ shooterId }: { shooterId: number }) {
  const query = useShooterSpecials(shooterId);
  // Sunday links keep the global round-type filter (C10).
  const href = useRoundTypeHref();
  if (query.data === undefined || query.data.length === 0) return null;
  const newestFirst = [...query.data].reverse();
  return (
    <Card title="Special shoots">
      <About explainer={eventExplainers.special} label="About special shoots" />
      <ul aria-label="Special shoots" className="flex flex-col divide-y divide-outline-variant">
        {newestFirst.map((s) => {
          const name = specialName(s);
          return (
            <li key={s.round_id}>
              <Link
                to={href(`/events/${s.event_date}`)}
                className="flex min-h-11 flex-wrap items-center justify-between gap-x-3 py-2"
              >
                <span className="font-medium">{formatDay(s.event_date)}</span>
                <span className="text-sm text-text-muted">
                  {`${name === null ? '' : `${name} · `}${specialTag(s)}`}
                </span>
                <span className="tabular-nums">{`${s.score} of ${s.target_total}`}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
