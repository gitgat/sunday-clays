import { useId, useState, type ReactNode } from 'react';
import { Link } from 'react-router';
import type { Explainer } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { ExplainerPanel, ExplainerToggle } from '../../../components/ui/Explainer';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { useClubRegulars } from '../api';
import type { CoreRegular, LapsedRegular } from '../api';
import { explainers } from '../explainers';
import { formatDay } from '../format';
import { formatShortDate } from '../../../lib/format';
import { useUnfilteredNote } from './roundTypeNote';

type Person = { shooter_id: number; display_name: string };

/** A profile link that keeps the global round-type filter (C10); 44px tall for touch. */
function ShooterLink({ person }: { person: Person }) {
  const to = useRoundTypeLink(`/shooters/${person.shooter_id}`);
  return (
    <Link
      to={to}
      className="inline-flex min-h-11 items-center text-accent underline-offset-2 hover:underline"
    >
      {person.display_name}
    </Link>
  );
}

/** Names shown before "Show all N". */
const SHOWN = 8;

/** One titled list; core and lapsed regulars are different row types, so `detail` formats each one. */
function PeopleList<T extends Person>({
  title,
  period,
  hint,
  explainer,
  people,
  detail,
}: {
  title: string;
  /** The fixed period the list counts over, e.g. "Last 12 months · to Sep 27". */
  period: string;
  hint: string;
  explainer: Explainer | undefined;
  people: T[];
  detail: (person: T) => string;
}) {
  const [open, setOpen] = useState(false);
  const [all, setAll] = useState(false);
  const panelId = useId();
  const shown = all ? people : people.slice(0, SHOWN);
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h4 className="font-medium">{`${title} (${people.length})`}</h4>
      <p className="text-sm">{period}</p>
      <p className="text-xs text-text-muted">{hint}</p>
      {explainer !== undefined && (
        <div>
          <ExplainerToggle
            label={`About ${title}`}
            panelId={panelId}
            open={open}
            onToggle={() => setOpen((v) => !v)}
          />
        </div>
      )}
      {open && explainer !== undefined && <ExplainerPanel id={panelId} explainer={explainer} />}
      {people.length === 0 ? (
        <p className="text-text-muted">None right now</p>
      ) : (
        <ul className="flex flex-col">
          {shown.map((p) => (
            <li key={p.shooter_id} className="flex items-center justify-between gap-x-3">
              <span className="min-w-0">
                <ShooterLink person={p} />
              </span>
              <span className="shrink-0 text-sm text-text-muted">{detail(p)}</span>
            </li>
          ))}
        </ul>
      )}
      {people.length > SHOWN && (
        <button
          type="button"
          aria-expanded={all}
          onClick={() => setAll((v) => !v)}
          className="min-h-11 self-start rounded-button px-1 text-sm text-accent underline underline-offset-2"
        >
          {all ? `Show fewer` : `Show all ${String(people.length)}`}
        </button>
      )}
    </section>
  );
}

export function RegularsCard() {
  const query = useClubRegulars();
  const note = useUnfilteredNote();
  let body: ReactNode;
  if (query.isPending) body = <Skeleton className="h-40" />;
  else if (query.isError)
    body = <EmptyState title="Couldn't load regulars" description={query.error.message} />;
  else {
    const { n_held_window: heldWindow, core, lapsed, as_of: asOf } = query.data;
    const upTo = `to ${formatShortDate(asOf)}`;
    body = (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <PeopleList<CoreRegular>
          title="Core regulars"
          period={`Last 12 months · ${upTo}`}
          hint="At half or more of the Sundays with full results in that year"
          explainer={explainers['regulars-core']}
          people={core}
          detail={(r) => `${r.events_attended} of ${heldWindow} Sundays`}
        />
        <PeopleList<LapsedRegular>
          title="Lapsed regulars"
          period={`Last 90 days · ${upTo}`}
          hint="Core regulars six months ago with no round in the last 90 days"
          explainer={explainers['regulars-lapsed']}
          people={lapsed}
          detail={(r) => `last out ${formatDay(r.last_event)}`}
        />
      </div>
    );
  }
  return (
    <Card
      title="Regulars"
      subtitle={`Counted back from the latest Sunday with scores; the time window doesn't apply${note === '' ? '' : ' · all round types'}`}
    >
      {body}
    </Card>
  );
}
