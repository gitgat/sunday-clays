import { Download } from 'lucide-react';
import { useState } from 'react';
import { ApiError } from '../../../api/errors';
import { Button } from '../../../components/ui/Button';
import { downloadBlob } from '../../../lib/download';
import { fetchScoresExport } from '../api';

function failureText(error: unknown): string {
  if (error instanceof ApiError && error.code === 'no_exportable_rounds') {
    return 'There are no Sunday rounds to export yet.';
  }
  return 'Could not export your scores. Try again.';
}

/**
 * Downloads the shooter's Sunday rounds as a zip of ClaySmasher Scores CSV files (one per
 * discipline), ready for the app's Settings › Import & export scores › Import from CSV.
 */
export function ExportScores({ shooterId }: { shooterId: number }) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function exportScores() {
    setFailure(null);
    setBusy(true);
    try {
      const { blob, filename } = await fetchScoresExport(shooterId);
      downloadBlob(blob, filename);
    } catch (error) {
      setFailure(failureText(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-1 self-start">
      <Button
        variant="tonal"
        loading={busy}
        icon={<Download aria-hidden="true" className="size-4" />}
        onClick={() => void exportScores()}
      >
        {busy ? 'Preparing your scores…' : 'Export my scores'}
      </Button>
      <p className="text-sm text-text-muted">
        One CSV per discipline, to import into the ClaySmasher app: Settings › Import & export
        scores › Import from CSV.
      </p>
      {failure !== null && (
        <p role="alert" className="text-sm">
          {failure}
        </p>
      )}
    </div>
  );
}
