import { useId, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { useCommitImport } from '../api';
import type { ImportPreview } from '../api';
import { AdminError } from './AdminError';
import { JobProgress } from './JobProgress';

/** Review Focus #1: with removals, Commit stays disabled until the admin confirms them; ERROR findings never block. */
export function CommitPanel({
  preview,
  onStarted,
  onSettled,
}: {
  preview: ImportPreview;
  /** The server accepted the commit (the import is `committed` from here on, whatever the rebuild does). */
  onStarted: () => void;
  /** The rebuild job finished, done or failed. */
  onSettled: () => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const commit = useCommitImport();
  const checkboxId = useId();
  const needsConfirm = preview.requires_removal_confirmation;

  return (
    <div className="flex flex-col gap-3">
      {needsConfirm && (
        <div className="flex min-h-11 items-center gap-2">
          <input
            id={checkboxId}
            type="checkbox"
            className="size-5"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          <label htmlFor={checkboxId} className="py-2.5">
            I understand this upload removes the events and rows listed above
          </label>
        </div>
      )}
      <Button
        disabled={(needsConfirm && !confirmed) || commit.isPending || commit.isSuccess}
        onClick={() =>
          commit.mutate(
            { id: preview.import_id, confirmRemovals: confirmed },
            { onSuccess: onStarted },
          )
        }
      >
        Commit import
      </Button>
      {commit.isError && <AdminError error={commit.error} />}
      {commit.isSuccess && (
        <JobProgress
          jobId={commit.data.job_id}
          label="Rebuilding live data"
          onSettled={onSettled}
        />
      )}
    </div>
  );
}
