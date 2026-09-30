import { Ribbon } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { cx } from '../../../components/ui/cx';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { Toggle } from '../../../components/ui/Toggle';
import { getMe } from '../../../lib/me';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { boolCodec, stringCodec, useUrlState } from '../../../lib/useUrlState';
import { useShooters } from '../api';
import type { ShooterListItem } from '../api';
import { formatDay, plural } from '../format';

function ShooterRow({ shooter, isMe }: { shooter: ShooterListItem; isMe: boolean }) {
  // C10: in-app links keep the global round-type filter (?rt=).
  const to = useRoundTypeLink(`/shooters/${shooter.shooter_id}`);
  return (
    <li>
      <Link
        to={to}
        className="flex min-h-11 flex-wrap items-center justify-between gap-x-3 px-4 py-2"
      >
        <span className="flex items-center gap-2">
          <span className="font-medium">{shooter.display_name}</span>
          {shooter.status === 'deceased' && (
            <span role="img" aria-label="In memoriam" className="text-accent">
              <Ribbon aria-hidden="true" className="size-4" />
            </span>
          )}
          {shooter.status === 'guest' && <span className="text-xs text-text-muted">Guest</span>}
          {isMe && <span className="rounded-button bg-primary px-2 text-xs">You</span>}
        </span>
        <span className="text-sm text-text-muted">
          {plural(shooter.n_events, 'Sunday')} · last {formatDay(shooter.last_event)}
        </span>
      </Link>
    </li>
  );
}

export function ShootersPage() {
  // Decision D19: search text and the Active-only toggle live in the URL (?q=, ?active=1).
  const [q, setQ] = useUrlState('q', stringCodec, '');
  const [active, setActive] = useUrlState('active', boolCodec, false);
  const search = useDeferredValue(q).trim();
  const shooters = useShooters(search, active);
  const me = getMe();
  // While a new search loads, the previous rows stay on screen (placeholder data), so an empty result keeps naming
  // the search it answered: `shownSearch` follows `search` only once that search's own result has arrived.
  const [shownSearch, setShownSearch] = useState(search);
  if (shooters.isSuccess && !shooters.isPlaceholderData && shownSearch !== search) {
    setShownSearch(search);
  }
  const updating = shooters.isPlaceholderData;

  let body: ReactNode;
  if (shooters.isPending) body = <Skeleton className="h-96" />;
  else if (shooters.isError)
    body = <EmptyState title="Couldn't load shooters" description={shooters.error.message} />;
  else if (shooters.data.length === 0)
    body = (
      <EmptyState title={shownSearch ? `No shooters match “${shownSearch}”` : 'No shooters yet'} />
    );
  else
    body = (
      <ul
        aria-label="Shooters"
        className="flex flex-col divide-y divide-outline-variant rounded-card bg-elevated"
      >
        {shooters.data.map((s) => (
          <ShooterRow key={s.shooter_id} shooter={s} isMe={s.shooter_id === me} />
        ))}
      </ul>
    );

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-medium">Shooters</h1>
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          aria-label="Search shooters"
          placeholder="Search by name"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="min-h-11 flex-1 rounded-button border border-outline-variant bg-elevated px-4"
        />
        <Toggle checked={active} onChange={setActive} label="Active only" />
      </div>
      <p className="-mt-2 text-sm text-text-muted">
        Active = shot in the last 12 months and has 5+ rounds
      </p>
      <div aria-busy={updating || undefined} className={cx(updating && 'opacity-60')}>
        {body}
      </div>
    </div>
  );
}
