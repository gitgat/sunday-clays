import { useId, useState } from 'react';
import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { useExplicitWindow } from '../../../lib/timeWindowChoice';
import { formatDay } from '../../shooters/format';
import type { Insight } from '../api';
import { chartHref } from '../chartLink';
import { Segments } from '../segments';
import { InsightCard } from './InsightCard';
import { isMine } from './InsightList';

export interface SheetLeadProps {
  /** The Sunday's hero pick (Home's "Top story"). */
  headline: Insight | null;
  /** The Sunday's pinned recap (Home's "Last Sunday"), shown as the headline's deck. */
  recap: Insight | null;
  /** The Sunday's "Shooter to know". */
  spotlight: Insight | null;
  meId: number | null;
  /** The issue's Sunday: a headline about an earlier Sunday names its date. */
  date: string;
}

/** "Sep 20, 2026 · not affected by the time filter" when the headline is about another Sunday. */
export function leadSubtitle(headline: Insight | null, date: string): string {
  const anchor = headline?.anchor_date ?? null;
  return anchor === null || anchor === date
    ? 'Not affected by the time filter'
    : `${formatDay(anchor)} · not affected by the time filter`;
}

/** The recap under the headline: clamped to 3 lines until "Show all", with its results link. */
function Deck({ recap }: { recap: Insight }) {
  const [all, setAll] = useState(false);
  const viewerWindow = useExplicitWindow();
  const deckId = useId();
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <p
        id={deckId}
        className={all ? 'text-base text-text-muted' : 'line-clamp-3 text-base text-text-muted'}
      >
        <Segments segments={recap.headline} />
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-expanded={all}
          aria-controls={deckId}
          onClick={() => setAll((v) => !v)}
          className="min-h-11 rounded-button px-3 text-sm text-text-muted hover:text-text"
        >
          {all ? 'Show less' : 'Show all'}
        </button>
        <Link
          to={chartHref(recap.chart, viewerWindow)}
          className="inline-flex min-h-11 items-center rounded-button px-3 text-sm text-accent hover:underline"
        >
          See the results
        </Link>
      </div>
    </div>
  );
}

/**
 * The Sheet's lead (Plan 14): the headline with the recap as its deck, then the spotlight. The
 * viewer's own single-shooter story reads in the second person. Picks may be about the Sunday
 * before the issue's; then the subtitle names that Sunday, as Home's "Top story" did. Nothing at all when the Sunday
 * has none of the three.
 */
export function SheetLead({ headline, recap, spotlight, meId, date }: SheetLeadProps) {
  if (headline === null && recap === null && spotlight === null) return null;
  return (
    <div className="flex min-w-0 flex-col gap-4">
      {(headline !== null || recap !== null) && (
        <Card title="Top story" subtitle={leadSubtitle(headline, date)}>
          <div className="flex min-w-0 flex-col gap-3">
            {headline !== null && (
              <ul aria-label="Top story" className="flex flex-col gap-3">
                <InsightCard insight={headline} you={isMine(headline, meId)} />
              </ul>
            )}
            {recap !== null && <Deck recap={recap} />}
          </div>
        </Card>
      )}
      {spotlight !== null && (
        <Card title="Spotlight" subtitle="Shooter to know">
          <ul aria-label="Spotlight" className="flex flex-col gap-3">
            <InsightCard insight={spotlight} you={isMine(spotlight, meId)} />
          </ul>
        </Card>
      )}
    </div>
  );
}
