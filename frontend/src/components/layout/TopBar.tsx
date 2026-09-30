import { Link } from 'react-router';
import { usePageFilters } from '../../lib/pageFilters';
import { useRoundTypeLink } from '../../lib/roundTypes';
import { RoundTypeFilter } from './RoundTypeFilter';
import { TimeWindowFilter } from './TimeWindowFilter';

/** Mobile (<1024px) top bar: brand, and the global round-type filter and time window the page honours. */
export function TopBar() {
  const home = useRoundTypeLink('/');
  const { roundType, window } = usePageFilters();
  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-1.5 border-b border-outline-variant bg-surface/95 px-4 py-2 backdrop-blur">
      <Link to={home} className="inline-flex min-h-11 items-center text-base font-bold text-text">
        Sunday Clays
      </Link>
      {roundType && <RoundTypeFilter align="right" />}
      {window && <TimeWindowFilter variant="select" />}
    </header>
  );
}
