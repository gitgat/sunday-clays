import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../../../components/ui/Button';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import { useDiscardImport } from '../api';
import type { ImportPreview } from '../api';
import { kindLabel, statusLabel } from '../format';
import { AdminError } from './AdminError';
import { CommitPanel } from './CommitPanel';
import { DiffSummary } from './DiffSummary';
import { FindingsList } from './FindingsList';

/**
 * Commit and discard only for a pending import (ERROR findings never block commit). A duplicate upload is the existing
 * import itself (Plan 03: `import_id === duplicate_of`), so its actions follow that import's status (Decision D14).
 */
export function ImportPreviewView({
  preview,
  status,
}: {
  preview: ImportPreview;
  status: string | undefined;
}) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const href = useRoundTypeHref();
  const discard = useDiscardImport();
  // Set as soon as the server accepts a commit from this page (it marks the import `committed` synchronously and
  // rebuilds in a job): the refreshed status then says `committed`, and the panel with its rebuild progress must stay
  // on screen rather than vanish with the pending status, even if the job fails or the list refetches meanwhile.
  const [committedHere, setCommittedHere] = useState(false);
  const pending = status === 'pending';
  const duplicate = preview.duplicate_of !== null;

  const refresh = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ['/api/admin/imports'] });
    void qc.invalidateQueries({ queryKey: ['/api/admin/imports/{id}', preview.import_id] });
  }, [qc, preview.import_id]);
  const onStarted = useCallback(() => {
    setCommittedHere(true);
    refresh();
  }, [refresh]);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-medium">{`Import #${preview.import_id}`}</h1>
        <p className="text-text-muted">
          {`${preview.filename} · ${kindLabel(preview.kind)} · ${status === undefined ? '…' : statusLabel(status)}`}
        </p>
      </header>
      {duplicate && (
        <p role="note" className="rounded-card border border-accent p-3">
          {pending
            ? `Already uploaded as import #${preview.duplicate_of}, which is still pending: review it below, then commit or discard it.`
            : `Already imported as import #${preview.duplicate_of}. Nothing to commit.`}
        </p>
      )}
      <DiffSummary diff={preview.diff} />
      <FindingsList findings={preview.findings} />
      {(pending || committedHere) && (
        <CommitPanel preview={preview} onStarted={onStarted} onSettled={refresh} />
      )}
      {pending && (
        <Button
          variant="tonal"
          disabled={discard.isPending}
          onClick={() =>
            discard.mutate(preview.import_id, {
              onSuccess: () => {
                refresh();
                void navigate(href('/admin'));
              },
            })
          }
        >
          Discard this upload
        </Button>
      )}
      {discard.isError && <AdminError error={discard.error} />}
    </div>
  );
}
