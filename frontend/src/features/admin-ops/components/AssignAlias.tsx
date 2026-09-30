import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import type { ShooterOption } from '../../admin/api';
import { AdminError } from '../../admin/components/AdminError';
import { JobProgress } from '../../admin/components/JobProgress';
import { ShooterPicker } from '../../admin/components/ShooterPicker';
import { useAssignAlias } from '../api';

/** Review Focus (master #2): an unmatched station name is fixed by aliasing its name key to a shooter. */
export function AssignAlias({ nameKey, rawName }: { nameKey: string; rawName: string }) {
  const [open, setOpen] = useState(false);
  const [shooter, setShooter] = useState<ShooterOption | null>(null);
  const assign = useAssignAlias();
  const qc = useQueryClient();
  const refresh = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ['/api/admin/data-issues'] });
  }, [qc]);

  const cancel = () => {
    setOpen(false);
    setShooter(null);
    assign.reset();
  };

  if (!open) {
    return (
      <Button variant="tonal" onClick={() => setOpen(true)}>
        Assign to shooter
      </Button>
    );
  }
  return (
    <div className="flex flex-col gap-2 rounded-card border border-outline-variant p-3">
      <ShooterPicker label={`Shooter for “${rawName}”`} value={shooter} onChange={setShooter} />
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={shooter === null || assign.isPending || assign.isSuccess}
          onClick={() => shooter && assign.mutate({ shooterId: shooter.shooter_id, nameKey })}
        >
          Assign
        </Button>
        <Button variant="ghost" onClick={cancel}>
          Cancel
        </Button>
      </div>
      {assign.isError && <AdminError error={assign.error} />}
      {assign.isSuccess && (
        <JobProgress
          jobId={assign.data.job_id}
          label={`Alias ${nameKey} → #${assign.variables.shooterId}`}
          onSettled={refresh}
        />
      )}
    </div>
  );
}
