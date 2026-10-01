import { useState } from 'react';
import { Link } from 'react-router';
import { useExplicitWindow } from '../../../lib/timeWindowChoice';
import { formatDay } from '../../shooters/format';
import { Card } from '../../../components/ui/Card';
import { InsightBump } from '../../bumps/BumpsProvider';
import type { Insight } from '../api';
import { chartHref } from '../chartLink';
import { Segments } from '../segments';

/** "Sep 27, 2026 · not affected by the time filter": a latest-Sunday card names its Sunday. */
export function latestSubtitle(date: string | null): string {
  return date === null
    ? 'Not affected by the time filter'
    : `${formatDay(date)} · not affected by the time filter`;
}

/** The pinned line about the latest Sunday, clamped to 3 lines until "Show all" (spec §3.8). */
export function RecapCard({ insight }: { insight: Insight }) {
  const [all, setAll] = useState(false);
  const viewerWindow = useExplicitWindow();
  return (
    <Card title="Last Sunday" subtitle={latestSubtitle(insight.anchor_date)}>
      <p className={all ? 'text-base text-text' : 'line-clamp-3 text-base text-text'}>
        <Segments segments={insight.headline} />
      </p>
      <div data-insight-key={insight.key} className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-expanded={all}
          onClick={() => setAll((v) => !v)}
          className="min-h-11 rounded-button px-3 text-sm text-text-muted hover:text-text"
        >
          {all ? 'Show less' : 'Show all'}
        </button>
        <Link
          to={chartHref(insight.chart, viewerWindow)}
          className="inline-flex min-h-11 items-center rounded-button px-3 text-sm text-accent hover:underline"
        >
          See the results
        </Link>
        <InsightBump insightKey={insight.key} />
      </div>
    </Card>
  );
}
