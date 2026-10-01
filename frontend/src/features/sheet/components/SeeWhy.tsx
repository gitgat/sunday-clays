import { Link } from 'react-router';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import { useExplicitWindow } from '../../../lib/timeWindowChoice';
import { chartHref } from '../../insights/chartLink';
import type { SheetPost } from '../api';

/**
 * "See why →": an insight post opens its chart, which scrolls into view and rings the evidence
 * (the Plan 12 chart-target link, never a round-type filter); a trophy post opens its Trophy Room
 * entry and an "On this day" post that Sunday's page, both keeping the global filters.
 */
export function SeeWhy({ post }: { post: SheetPost }) {
  const viewerWindow = useExplicitWindow();
  const withFilters = useRoundTypeHref();
  const why = post.see_why;
  const to =
    why.kind === 'chart' && why.chart != null
      ? chartHref(why.chart, viewerWindow)
      : withFilters(why.href ?? '/');
  return (
    <Link
      to={to}
      aria-label={`See why: ${why.label}`}
      className="inline-flex min-h-11 items-center rounded-button px-3 text-sm text-accent hover:underline"
    >
      See why →
    </Link>
  );
}
