import { Button } from '../../../components/ui/Button';
import { Skeleton } from '../../../components/ui/Skeleton';
import { AdminError } from '../../admin/components/AdminError';
import { formatTimestamp } from '../../admin/format';
import { useAudit } from '../api';

export function detailsSummary(details: Record<string, unknown>): string {
  return Object.entries(details)
    .map(
      ([key, value]) =>
        `${key}=${typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)}`,
    )
    .join(', ');
}

export function AuditLog() {
  const audit = useAudit();
  if (audit.isPending) return <Skeleton className="h-40" />;
  if (audit.isError) return <AdminError error={audit.error} />;
  // Offset paging over a newest-first log: a row logged between two pages repeats the last row of the
  // previous one, so keep each id once.
  const entries = [...new Map(audit.data.pages.flat().map((e) => [e.id, e])).values()];
  if (entries.length === 0) return <p className="text-text-muted">No admin actions yet.</p>;
  return (
    // Explicit roles: below `sm` the table, rows and cells are stacked cards (display: block/flex), which would
    // otherwise drop the table semantics. Each card reads: when, then role · action · IP, then the details.
    <div className="min-w-0">
      <table aria-label="Audit log" role="table" className="w-full text-sm max-sm:block">
        <thead role="rowgroup" className="text-left text-text-muted max-sm:sr-only">
          <tr role="row">
            {['When', 'Role', 'Action', 'IP', 'Details'].map((h) => (
              <th key={h} role="columnheader" scope="col" className="py-2 pr-2">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody role="rowgroup" className="max-sm:flex max-sm:flex-col">
          {[...entries]
            .sort((a, b) => b.id - a.id)
            .map((entry) => (
              <tr
                key={entry.id}
                role="row"
                className="border-t border-outline-variant align-top max-sm:flex max-sm:flex-wrap max-sm:gap-x-3 max-sm:py-2"
              >
                <td
                  role="cell"
                  className="py-2 pr-2 whitespace-nowrap max-sm:basis-full max-sm:py-0"
                >
                  {formatTimestamp(entry.at)}
                </td>
                <td role="cell" className="py-2 pr-2 max-sm:py-0">
                  {entry.role}
                </td>
                <td role="cell" className="min-w-0 py-2 pr-2 [overflow-wrap:anywhere] max-sm:py-0">
                  {entry.action}
                </td>
                <td role="cell" className="py-2 pr-2 max-sm:py-0">
                  {entry.ip ?? '—'}
                </td>
                <td
                  role="cell"
                  className="min-w-0 py-2 [overflow-wrap:anywhere] max-sm:basis-full max-sm:py-0 max-sm:text-text-muted"
                >
                  {detailsSummary(entry.details)}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <p className="text-sm text-text-muted">Showing the latest {entries.length}</p>
        {audit.hasNextPage ? (
          <Button
            variant="tonal"
            loading={audit.isFetchingNextPage}
            onClick={() => void audit.fetchNextPage()}
          >
            Load more
          </Button>
        ) : null}
      </div>
    </div>
  );
}
