import { usePageFilters } from '../../lib/pageFilters';
import { RoundTypeFilter } from './RoundTypeFilter';
import { TimeWindowFilter } from './TimeWindowFilter';

/**
 * Desktop (≥1024px) filter bar: the global round type and time window, sticky at the top of the
 * main content so they sit beside the page rather than in the navigation. It shows only the filters
 * the page honours (its route's `handle.filters`), and nothing at all for a page that honours
 * neither. The phone/tablet layout keeps them in the TopBar.
 */
export function ContentHeader() {
  const { roundType, window } = usePageFilters();
  if (!roundType && !window) return null;
  return (
    <div
      role="group"
      aria-label="Page filters"
      className="sticky top-0 z-30 border-b border-outline-variant bg-surface/95 backdrop-blur"
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-end gap-x-4 gap-y-1 px-6 py-2">
        {roundType && <RoundTypeFilter align="right" />}
        {window && <TimeWindowFilter />}
      </div>
    </div>
  );
}
