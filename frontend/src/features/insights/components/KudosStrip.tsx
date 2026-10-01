import { useState } from 'react';
import { Link } from 'react-router';
import { Sheet } from '../../../components/ui/Sheet';
import { InsightBump } from '../../bumps/BumpsProvider';
import { useIsDesktop } from '../../../lib/useMediaQuery';
import type { InsightKudos } from '../api';
import { Segments } from '../segments';
import { InsightCard } from './InsightCard';

/** At most this many chips show; the rest open from an "and N more" chip (D10, spec §3.4). */
export const KUDOS_CAP = 10;

/** What each kudos kind celebrates, in a few words about the shooter alone (D1, D9). */
const KUDOS_LABELS: Record<string, string> = {
  'lb.biggest-climb': 'big climb on the board',
  'lb.most-improved': 'most improved',
  'pf.above-own-avg-streak': 'run above own average',
  'pf.average-milestone': 'average milestone',
  'pf.beat-field-streak': 'run above the field',
  'pf.beat-own-usual': 'well above own usual',
  'pf.best-stretch': 'best stretch yet',
  'pf.career-first': 'a career first',
  'pf.first-since': 'first in a while',
  'pf.first-tier': 'a first at a new mark',
  'pf.high-round-count': 'high-round milestone',
  'pf.more-high-rounds': 'more high rounds',
  'pf.pb': 'personal best',
  'pf.podium-run': 'podium run',
  'pf.sunday-milestone': 'Sunday milestone',
  'pf.targets-milestone': 'targets milestone',
  'pf.three-rising': 'three rising',
  'pf.tied-best': 'tied own best',
  'pf.tier-run': 'run at their mark',
  'pf.wins': 'a win',
};

/** The chip's short label for a kudos insight ("kudos" for a kind added later). */
export function kudosLabel(kind: string): string {
  return KUDOS_LABELS[kind] ?? 'kudos';
}

/** "Last, First" as "First Last" (the names in headlines read the same way). */
export function naturalName(displayName: string): string {
  const [last, first] = displayName.split(',', 2).map((part) => part.trim());
  return first ? `${first} ${last ?? ''}`.trim() : displayName.trim();
}

const CHIP =
  'inline-flex min-h-11 items-center rounded-button border border-outline-variant px-3 text-left text-sm text-text hover:border-accent';

/**
 * Kudos: a chip per shooter with something to celebrate ("Pat Kim · personal best"); a tap opens
 * that insight in a Sheet. Stats about each shooter only, never a comparison between them.
 * Hidden when there are none.
 */
export function KudosStrip({
  kudos,
  meId,
  title = 'Kudos',
}: {
  kudos: readonly InsightKudos[];
  meId: number | null;
  /** "This week's kudos" on home; "Kudos" on a Sunday. */
  title?: string;
}) {
  const [all, setAll] = useState(false);
  const [chosen, setChosen] = useState<InsightKudos | null>(null);
  const isDesktop = useIsDesktop();
  if (kudos.length === 0) return null;
  const shown = kudos.slice(0, KUDOS_CAP);
  const more = kudos.length - shown.length;
  const placement = isDesktop ? 'center' : 'bottom';
  return (
    <section aria-label={title} className="flex min-w-0 flex-col gap-2">
      <h3 className="text-sm font-medium text-text-muted">{title}</h3>
      <ul className="flex flex-wrap gap-2">
        {shown.map((chip) => (
          <li key={chip.shooter_id}>
            <button type="button" className={CHIP} onClick={() => setChosen(chip)}>
              {`${naturalName(chip.display_name)} · ${kudosLabel(chip.insight.kind)}`}
            </button>
          </li>
        ))}
        {more > 0 && (
          <li>
            <button type="button" className={CHIP} onClick={() => setAll(true)}>
              {`and ${String(more)} more`}
            </button>
          </li>
        )}
      </ul>
      <Sheet
        open={chosen !== null}
        onClose={() => setChosen(null)}
        title={chosen === null ? title : naturalName(chosen.display_name)}
        placement={placement}
      >
        {chosen !== null && (
          <ul className="flex flex-col gap-3">
            <InsightCard insight={chosen.insight} you={meId === chosen.shooter_id} />
          </ul>
        )}
      </Sheet>
      <Sheet open={all} onClose={() => setAll(false)} title={title} placement={placement}>
        <ul className="flex flex-col gap-3">
          {kudos.map((chip) => {
            const you = meId === chip.shooter_id && chip.insight.headline_you !== null;
            return (
              <li
                key={chip.shooter_id}
                data-insight-key={chip.insight.key}
                className="flex flex-col gap-1"
              >
                <Link
                  to={`/shooters/${String(chip.shooter_id)}`}
                  className="inline-flex min-h-11 items-center self-start font-medium text-text underline-offset-2 hover:underline"
                >
                  {naturalName(chip.display_name)}
                </Link>
                <p className="text-sm text-text-muted">
                  <Segments
                    segments={you ? (chip.insight.headline_you ?? []) : chip.insight.headline}
                  />
                </p>
                <InsightBump insightKey={chip.insight.key} />
              </li>
            );
          })}
        </ul>
      </Sheet>
    </section>
  );
}
