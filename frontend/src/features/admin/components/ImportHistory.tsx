import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';
import { Link } from 'react-router';
import { Button } from '../../../components/ui/Button';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { useDiscardImport, useImports, useRollbackImport } from '../api';
import type { ImportSummary } from '../api';
import { formatTimestamp, kindLabel, statusLabel } from '../format';
import { AdminError } from './AdminError';
import { JobProgress } from './JobProgress';

/** A row's link to its preview; keeps the global round-type filter (C10). */
function ImportLink({ imp }: { imp: ImportSummary }) {
  const to = useRoundTypeLink(`/admin/imports/${imp.id}`);
  return (
    <Link
      to={to}
      className="inline-flex min-h-11 items-center text-accent [overflow-wrap:anywhere] underline-offset-2 hover:underline"
    >
      {imp.filename}
    </Link>
  );
}

export function ImportHistory() {
  const imports = useImports();
  const discard = useDiscardImport();
  const rollback = useRollbackImport();
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState<number | null>(null);
  const [rollbackJob, setRollbackJob] = useState<{ importId: number; jobId: number } | null>(null);
  const refresh = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ['/api/admin/imports'] });
  }, [qc]);

  if (imports.isPending) return <Skeleton className="h-40" />;
  if (imports.isError) return <AdminError error={imports.error} />;
  if (imports.data.length === 0) {
    return <p className="text-text-muted">No imports yet — upload a workbook to start.</p>;
  }

  function actions(imp: ImportSummary) {
    if (imp.status === 'pending') {
      return (
        <Button
          variant="tonal"
          disabled={discard.isPending}
          onClick={() => discard.mutate(imp.id, { onSuccess: refresh })}
        >
          Discard
        </Button>
      );
    }
    // While its rollback job runs the row offers nothing, even if the list has not refetched yet.
    if (imp.status !== 'committed' || rollbackJob?.importId === imp.id) return null;
    if (confirming !== imp.id) {
      return (
        <Button variant="tonal" onClick={() => setConfirming(imp.id)}>
          Roll back
        </Button>
      );
    }
    return (
      <span className="flex flex-wrap gap-2">
        <Button
          disabled={rollback.isPending}
          onClick={() =>
            rollback.mutate(imp.id, {
              onSuccess: (result) => {
                setConfirming(null);
                refresh();
                setRollbackJob({ importId: imp.id, jobId: result.job_id });
              },
            })
          }
        >
          Confirm roll back
        </Button>
        <Button variant="ghost" onClick={() => setConfirming(null)}>
          Cancel
        </Button>
      </span>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {rollbackJob !== null && (
        <JobProgress
          jobId={rollbackJob.jobId}
          label={`Rolling back #${rollbackJob.importId}`}
          onSettled={refresh}
        />
      )}
      {discard.isError && <AdminError error={discard.error} />}
      {rollback.isError && <AdminError error={rollback.error} />}
      {/*
        Explicit roles: below `sm` the table, rows and cells are laid out as stacked cards (display: block), which
        would otherwise drop the table semantics. Each card reads: file name, then # · kind · status · uploaded, then
        the actions on their own line.
      */}
      <table aria-label="Import history" role="table" className="w-full text-sm max-sm:block">
        <thead role="rowgroup" className="text-left text-text-muted max-sm:sr-only">
          <tr role="row">
            {['#', 'File', 'Kind', 'Status', 'Uploaded', 'Actions'].map((h) => (
              <th key={h} role="columnheader" scope="col" className="py-2 pr-2">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody role="rowgroup" className="max-sm:flex max-sm:flex-col">
          {[...imports.data]
            .sort((a, b) => b.id - a.id)
            .map((imp) => (
              <tr
                key={imp.id}
                role="row"
                className="border-t border-outline-variant max-sm:flex max-sm:flex-wrap max-sm:items-center max-sm:gap-x-3 max-sm:py-2"
              >
                <td role="cell" className="py-2 pr-2 tabular-nums max-sm:py-0">{`#${imp.id}`}</td>
                <td
                  role="cell"
                  className="min-w-0 py-2 pr-2 max-sm:order-first max-sm:basis-full max-sm:py-0"
                >
                  <ImportLink imp={imp} />
                </td>
                <td role="cell" className="py-2 pr-2 max-sm:py-0">
                  {kindLabel(imp.kind)}
                </td>
                <td role="cell" className="py-2 pr-2 max-sm:py-0">
                  {statusLabel(imp.status)}
                </td>
                <td role="cell" className="py-2 pr-2 max-sm:py-0">
                  {formatTimestamp(imp.uploaded_at)}
                </td>
                <td role="cell" className="py-2 max-sm:basis-full max-sm:py-0">
                  {actions(imp)}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
