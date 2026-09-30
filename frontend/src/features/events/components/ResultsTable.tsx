import { Link } from 'react-router';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import type { EventResult } from '../api';
import { formatSigned } from '../format';

/** Rank label per round: min-rank on best rounds ('T<n>' when shared), '—' on every other round (D8). */
export function rankLabels(results: EventResult[]): Map<number, string> {
  const shared = new Map<number, number>();
  for (const r of results) {
    if (r.is_best_round && r.event_rank !== null) {
      shared.set(r.event_rank, (shared.get(r.event_rank) ?? 0) + 1);
    }
  }
  return new Map(
    results.map((r): [number, string] => {
      if (!r.is_best_round || r.event_rank === null) return [r.round_id, '—'];
      return [
        r.round_id,
        shared.get(r.event_rank) === 1 ? String(r.event_rank) : `T${r.event_rank}`,
      ];
    }),
  );
}

/**
 * Decision D8: the server's rating_delta (mu_after − mu_before) on the best round only; null → '—'.
 * A partial-results Sunday is not rated (ratings do not move), so it shows '—', never 0.0.
 */
export function ratingDelta(r: EventResult, complete = true): string {
  return complete && r.is_best_round ? formatSigned(r.rating_delta) : '—';
}

/** `s:{id}` items of an insight link's `hl`, as shooter ids (Plan 12 chart targets). */
export function highlightedShooters(hl: readonly string[]): Set<number> {
  return new Set(hl.filter((k) => k.startsWith('s:')).map((k) => Number(k.slice(2))));
}

export function ResultsTable({
  results,
  complete = true,
  highlight,
}: {
  results: EventResult[];
  /** The Sunday's results are complete; when false the rating change is not shown. */
  complete?: boolean;
  /** Shooters an insight points to: their rows are marked (Plan 12). */
  highlight?: ReadonlySet<number>;
}) {
  // Profile links keep the global round-type filter (C10).
  const href = useRoundTypeHref();
  const labels = rankLabels(results);
  const sorted = [...results].sort(
    (a, b) =>
      b.score - a.score || a.display_name.localeCompare(b.display_name) || a.ordinal - b.ordinal,
  );
  return (
    <div className="overflow-x-auto">
      <table aria-label="Results" className="w-full text-sm">
        <thead className="text-left text-text-muted">
          <tr>
            <th scope="col" className="py-2 pr-2">
              Rank
            </th>
            <th scope="col" className="py-2 pr-2">
              Shooter
            </th>
            <th scope="col" className="py-2 pr-2 text-right">
              Score
            </th>
            <th scope="col" className="py-2 pr-2 text-right">
              Vs middle score
            </th>
            <th scope="col" className="py-2 text-right">
              Rating change
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr
              key={r.round_id}
              aria-current={highlight?.has(r.shooter_id) === true ? 'true' : undefined}
              className={
                highlight?.has(r.shooter_id) === true
                  ? 'border-t border-outline-variant bg-accent/15 font-medium'
                  : 'border-t border-outline-variant'
              }
            >
              <td className="py-2 pr-2 tabular-nums">{labels.get(r.round_id)}</td>
              <td className="pr-2">
                {/* C10: a 44 px tap target (it sets the row height) and underlined without hover. */}
                <Link
                  to={href(`/shooters/${r.shooter_id}`)}
                  className="inline-flex min-h-11 min-w-11 items-center underline underline-offset-2"
                >
                  {r.display_name}
                </Link>
                {r.ordinal > 1 && (
                  <span
                    title="Additional round that day"
                    className="ml-2 rounded-button border border-outline-variant px-2 text-xs"
                  >
                    R{r.ordinal}
                  </span>
                )}
              </td>
              <td className="py-2 pr-2 text-right tabular-nums">{r.score}</td>
              <td className="py-2 pr-2 text-right tabular-nums">{formatSigned(r.adjusted)}</td>
              <td className="py-2 text-right tabular-nums">{ratingDelta(r, complete)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
