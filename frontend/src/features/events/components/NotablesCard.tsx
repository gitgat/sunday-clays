import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import type { Notable } from '../api';
import { eventExplainers } from '../explainers';
import { About } from './About';

// NotableOut.kind is 'pb' | 'first_timer'; both are told by the Sunday's insights (`pf.pb`,
// `ev.new-faces`, Plan 12), so only a kind a newer server adds shows here, verbatim.
const TOLD_BY_INSIGHTS = new Set(['pb', 'first_timer']);

export function NotablesCard({ notables: all }: { notables: Notable[] }) {
  const href = useRoundTypeHref();
  const notables = all.filter((n) => !TOLD_BY_INSIGHTS.has(n.kind));
  if (notables.length === 0) return null;
  return (
    <Card title="Notables">
      <About explainer={eventExplainers.notables} label="About notables" />
      <ul className="flex flex-col gap-2">
        {notables.map((n, i) => (
          <li key={`${n.kind}-${n.shooter_id}-${i}`}>
            <span className="font-medium">{n.kind}</span>
            {': '}
            <Link
              to={href(`/shooters/${n.shooter_id}`)}
              className="inline-flex min-h-11 min-w-11 items-center underline underline-offset-2"
            >
              {n.display_name}
            </Link>
            {` — ${n.detail}`}
          </li>
        ))}
      </ul>
    </Card>
  );
}
