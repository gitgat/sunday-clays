import type { components } from '../../api/schema';
import { formatDate } from '../../lib/format';
import { useTimeWindow } from '../../lib/timeWindow';
import type { EraSel } from './api';
import { inPeriod, scopeText, useStationWindow } from './window';

type Coverage = components['schemas']['StationCoverageOut'];
type ShooterCoverage = components['schemas']['ShooterStationCoverageOut'];

/** Below this share of scored Sundays the station data is called a small sample. */
const SMALL_SHARE = 0.25;

const sundays = (n: number): string => `${n} ${n === 1 ? 'Sunday' : 'Sundays'}`;

const spanOf = (first: string | null, last: string | null): string =>
  first === last ? formatDate(first) : `${formatDate(first)} – ${formatDate(last)}`;

/** What the numbers on a stations page cover: the setups, the time window and its dates. */
export function ScopeLine({ era }: { era: EraSel }) {
  const { window, range } = useTimeWindow();
  return (
    <p
      role="note"
      aria-label="Setups and dates shown"
      className="min-w-0 text-sm font-medium text-text-muted"
    >
      {scopeText(era, window, range)}
    </p>
  );
}

/**
 * A muted info note: station hits come only from the station sheets, so they can cover fewer
 * Sundays than the scored history. Both counts are inside the time window; the small-sample wording
 * shows only while station Sundays are under a quarter of the scored ones. Nothing is shown when
 * there are no station Sundays (the page's own empty state says so).
 */
export function CoverageNote({ coverage, filtered }: { coverage: Coverage; filtered: boolean }) {
  const { window } = useStationWindow();
  const { n_station_sundays: n, first_date: first, last_date: last } = coverage;
  if (n === 0) return null;
  const total = coverage.n_scored_sundays;
  const small = n / total < SMALL_SHARE;
  return (
    <p
      role="note"
      aria-label="Station data coverage"
      className="min-w-0 rounded-card border border-outline-variant bg-elevated px-3 py-2 text-sm text-text-muted"
    >
      Station scores cover {n} of {sundays(total)} {inPeriod(window)} ({spanOf(first, last)}
      ).
      {small
        ? ' Older station sheets weren’t kept, so these numbers rest on a small sample and will firm up as new Sundays are added.'
        : ''}
      {filtered ? ' Counts follow the round types you picked.' : ''}
    </p>
  );
}

/** The one-line profile note: it counts this shooter’s own station rounds, not the club’s. */
export function ShooterCoverageNote({
  coverage,
  filtered,
}: {
  coverage: ShooterCoverage;
  filtered: boolean;
}) {
  const { window } = useStationWindow();
  const { n_rounds: rounds, n_sundays: n } = coverage;
  if (n === 0) return null;
  return (
    <p
      role="note"
      aria-label="Station data coverage"
      className="min-w-0 rounded-card border border-outline-variant bg-elevated px-3 py-2 text-sm text-text-muted"
    >
      Station scores for this shooter: {rounds} {rounds === 1 ? 'round' : 'rounds'} on {sundays(n)}{' '}
      {inPeriod(window)} ({spanOf(coverage.first_date, coverage.last_date)}).
      {filtered ? ' Counts follow the round types you picked.' : ''}
    </p>
  );
}
