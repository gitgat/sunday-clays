import { useState } from 'react';
import { Link } from 'react-router';

import { rowTargeted } from '../../../components/charts/chartTarget';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import type { LeaderboardMetric, LeaderboardRowOut } from '../api';
import { countLabel, formatValue, metricLabel } from '../labels';

export interface StandingsTableProps {
  rows: readonly LeaderboardRowOut[];
  metric: LeaderboardMetric;
  /** An insight link's `lb-board.hl` keys (`s:{id}`): those rows are ringed (Plan 12). */
  highlight?: readonly string[];
}

/** The shooter's name as a profile link; a component so it can call the hook that keeps `?rt=` (C10). */
function ShooterLink({ row }: { row: LeaderboardRowOut }) {
  const to = useRoundTypeLink(`/shooters/${String(row.shooter_id)}`);
  return (
    <Link
      to={to}
      className="inline-flex min-h-11 items-center underline underline-offset-2 hover:text-accent"
    >
      {row.display_name}
    </Link>
  );
}

/** Rows shown before "Show all N". */
export const STANDINGS_ROWS = 10;

export function StandingsTable({ rows, metric, highlight = [] }: StandingsTableProps) {
  const [all, setAll] = useState(false);
  const capped = !all && rows.length > STANDINGS_ROWS;
  const shown = capped ? rows.slice(0, STANDINGS_ROWS) : rows;
  const edge = shown.at(-1);
  // "3 more tied at 44.50": rows the cut left out that share the last shown value.
  const tied =
    capped && edge !== undefined
      ? rows.slice(STANDINGS_ROWS).filter((r) => r.value === edge.value).length
      : 0;
  return (
    <>
      <table aria-label="Leaderboard standings" className="w-full text-left text-sm">
        <thead className="text-text-muted">
          <tr>
            <th scope="col" className="w-12 py-2">
              #
            </th>
            <th scope="col">Shooter</th>
            <th scope="col" className="text-right">
              {metricLabel(metric)}
            </th>
            <th scope="col" className="text-right">
              {countLabel(metric)}
            </th>
          </tr>
        </thead>
        <tbody>
          {shown.map((row) => (
            <tr
              key={row.shooter_id}
              aria-current={rowTargeted(highlight, row.shooter_id, null) ? 'true' : undefined}
              className={
                rowTargeted(highlight, row.shooter_id, null)
                  ? 'border-t border-outline-variant bg-accent/15 font-medium'
                  : 'border-t border-outline-variant'
              }
            >
              <td className="py-2 tabular-nums">{row.rank}</td>
              <td className="min-w-0 break-words">
                <ShooterLink row={row} />
              </td>
              <td className="text-right tabular-nums">{formatValue(metric, row.value)}</td>
              <td className="text-right tabular-nums text-text-muted">{row.n_rounds}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {capped && (
        <div className="flex flex-wrap items-center gap-3 pt-2 text-sm text-text-muted">
          {tied > 0 && edge !== undefined && (
            <span>
              {String(tied)} more tied at {formatValue(metric, edge.value)}
            </span>
          )}
          <button
            type="button"
            onClick={() => {
              setAll(true);
            }}
            className="inline-flex min-h-11 items-center rounded-button px-2 text-accent underline underline-offset-2"
          >
            Show all {String(rows.length)}
          </button>
        </div>
      )}
    </>
  );
}
