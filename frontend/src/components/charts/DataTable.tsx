import { Link } from 'react-router';
import { formatNumber } from '../../lib/format';
import { useRoundTypeHref } from '../../lib/roundTypes';
import type { Cell, TabularColumn, TabularRow } from './types';

/** 'int' cells (years, ids, stations, counts) print as-is; 'number' cells get grouping and ≤2 dp. */
function formatCell(value: Cell | undefined, column: TabularColumn): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    if (column.type === 'int' && Number.isInteger(value)) return String(value);
    return formatNumber(value, Number.isInteger(value) ? 0 : 2);
  }
  return value;
}

export interface DataTableProps {
  caption: string;
  columns: readonly TabularColumn[];
  rows: readonly TabularRow[];
  /**
   * Drill-down: links one cell of each row, the `rowHrefKey` column's, else the first text
   * column's (else the first cell). The global round-type filter is added to the href (C10), so a
   * caller returns a plain path.
   */
  rowHref?: ((row: TabularRow) => string) | undefined;
  /**
   * Key of the column whose cell carries the link, when the default would pick the wrong one
   * (an event date followed by a text column); no link when no column has this key.
   */
  rowHrefKey?: string | undefined;
}

/** The "Table" view of a chart: the exact rows behind it. */
export function DataTable({ caption, columns, rows, rowHref, rowHrefKey }: DataTableProps) {
  const drillHref = useRoundTypeHref();
  const linkIndex =
    rowHrefKey === undefined
      ? Math.max(
          0,
          columns.findIndex((c) => c.type === 'string'),
        )
      : columns.findIndex((c) => c.key === rowHrefKey);
  return (
    // A focusable scroll region, so keyboard users can scroll a long or wide table.
    <div
      className="max-h-96 overflow-auto"
      tabIndex={0}
      role="region"
      aria-label={`${caption} table`}
    >
      <table className="w-full border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 bg-elevated">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={`border-b border-outline-variant px-2 py-2 font-medium text-text-muted ${c.type === 'number' || c.type === 'int' ? 'text-right' : ''}`}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-outline-variant/40">
              {columns.map((c, j) => {
                const text = formatCell(row[c.key], c);
                const numericCol = c.type === 'number' || c.type === 'int';
                return (
                  <td
                    key={c.key}
                    className={`px-2 py-2 ${numericCol ? 'text-right tabular-nums' : ''}`}
                  >
                    {j === linkIndex && rowHref ? (
                      <Link
                        to={drillHref(rowHref(row))}
                        className="text-accent underline-offset-2 hover:underline"
                      >
                        {text}
                      </Link>
                    ) : (
                      text
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
