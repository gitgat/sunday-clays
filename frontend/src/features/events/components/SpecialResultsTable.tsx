import { Link } from 'react-router';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import type { EventResult } from '../api';

/**
 * Plan 17 (Decision 20): a special shoot's results as entered, best first. Nobody is ranked or rated
 * there, so the table is the shooter and the score out of the shoot's own total.
 */
export function SpecialResultsTable({
  results,
  targetTotal,
}: {
  results: EventResult[];
  targetTotal: number;
}) {
  // Profile links keep the global round-type filter (C10).
  const href = useRoundTypeHref();
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
              Shooter
            </th>
            <th scope="col" className="py-2 text-right">
              {`Score (of ${targetTotal})`}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.round_id} className="border-t border-outline-variant">
              <td className="pr-2">
                <Link
                  to={href(`/shooters/${r.shooter_id}`)}
                  className="inline-flex min-h-11 min-w-11 items-center underline underline-offset-2"
                >
                  {r.display_name}
                </Link>
              </td>
              <td className="py-2 text-right tabular-nums">{r.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
