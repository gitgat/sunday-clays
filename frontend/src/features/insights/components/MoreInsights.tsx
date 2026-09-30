import { useContext } from 'react';
import { CardHeadingLevel } from '../../../components/ui/Card';
import type { Insight } from '../api';
import { InsightCard } from './InsightCard';
import { isMine } from './InsightList';

const FAMILY_LABELS: Record<string, string> = {
  form: 'Form',
  streak: 'Streaks',
  milestone: 'Milestones',
  race: 'The race',
  record: 'Records',
  weather: 'Weather and the day',
  turnout: 'Turnout',
  newcomer: 'New faces',
  station: 'Stations',
  trophy: 'Trophies',
  recap: 'Recaps',
};

/** Everything else for the page, grouped by family, closed until asked for (spec §3.4). */
export function MoreInsights({
  items,
  total,
  you = false,
  meId = null,
  onShowAll,
  loadingAll = false,
}: {
  items: readonly Insight[];
  /** All the page's other insights (the list is capped at 30). */
  total: number;
  you?: boolean;
  /** On shared pages, the viewer's own single-shooter cards read in the second person. */
  meId?: number | null;
  /** When given, a "Show all N" button asks for the rest of the list (the page's list is capped). */
  onShowAll?: () => void;
  /** True while the full list is loading after a tap: the button is disabled and says so. */
  loadingAll?: boolean;
}) {
  const level = useContext(CardHeadingLevel) + 1;
  const Heading = level === 3 ? 'h3' : 'h4';
  if (items.length === 0) return null;
  const families = [...new Set(items.map((i) => i.family))];
  return (
    <details className="min-w-0">
      <summary className="min-h-11 cursor-pointer py-2 text-sm font-medium text-text">
        {`More insights (${String(total)})`}
      </summary>
      <div className="flex flex-col gap-4 pt-2">
        {families.map((family) => (
          <section key={family} aria-label={FAMILY_LABELS[family] ?? family}>
            <Heading className="mb-2 text-sm text-text-muted">
              {FAMILY_LABELS[family] ?? family}
            </Heading>
            <ul className="flex flex-col gap-3">
              {items
                .filter((i) => i.family === family)
                .map((i) => (
                  <InsightCard key={i.key} insight={i} you={you || isMine(i, meId)} />
                ))}
            </ul>
          </section>
        ))}
        {total > items.length && onShowAll !== undefined && (
          <button
            type="button"
            onClick={onShowAll}
            disabled={loadingAll}
            className="min-h-11 self-start rounded-button px-1 text-sm text-accent underline underline-offset-2 disabled:no-underline disabled:opacity-60"
          >
            {loadingAll ? 'Loading…' : `Show all ${String(total)}`}
          </button>
        )}
        {total > items.length && onShowAll === undefined && (
          <p className="text-sm text-text-muted">{`Showing ${String(items.length)} of ${String(total)}.`}</p>
        )}
      </div>
    </details>
  );
}
