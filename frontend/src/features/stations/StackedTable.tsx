import type { ReactNode } from 'react';

export interface StackedRow {
  key: string | number;
  /** The row header cell (e.g. "Station 9"). */
  header: string;
  cells: ReactNode[];
}

/**
 * A table on desktop; on a phone each row becomes a card with `label  value` lines, so nothing
 * scrolls sideways. Roles are explicit because `display: block` can drop the table semantics.
 */
export function StackedTable({
  caption,
  headers,
  rows,
}: {
  caption: string;
  /** Column headers; the first names the row header column. */
  headers: string[];
  rows: StackedRow[];
}) {
  const [first = '', ...rest] = headers;
  return (
    <table role="table" className="block w-full text-sm md:table">
      <caption className="sr-only">{caption}</caption>
      <thead role="rowgroup" className="max-md:sr-only md:table-header-group">
        <tr role="row" className="md:table-row">
          <th role="columnheader" scope="col" className="py-2 pr-3 text-left text-text-muted">
            {first}
          </th>
          {rest.map((label) => (
            <th
              key={label}
              role="columnheader"
              scope="col"
              className="py-2 pr-3 text-right text-text-muted"
            >
              {label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody role="rowgroup" className="block md:table-row-group">
        {rows.map((row) => (
          <tr
            key={row.key}
            role="row"
            className="block border-t border-outline-variant py-2 md:table-row"
          >
            <th
              role="rowheader"
              scope="row"
              className="block pb-1 text-left font-medium md:table-cell md:py-2 md:pr-3"
            >
              {row.header}
            </th>
            {row.cells.map((cell, i) => (
              <td
                key={i}
                role="cell"
                data-label={rest[i]}
                className="flex justify-between gap-4 py-0.5 tabular-nums before:text-text-muted before:content-[attr(data-label)] md:table-cell md:py-2 md:pr-3 md:text-right md:before:content-none"
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
