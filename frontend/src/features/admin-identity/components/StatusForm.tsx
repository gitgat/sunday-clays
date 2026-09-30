import { useState } from 'react';
import { Button } from '../../../components/ui/Button';
import type { ShooterOption } from '../../admin/api';
import { AdminError } from '../../admin/components/AdminError';
import { JobProgress } from '../../admin/components/JobProgress';
import { ShooterPicker } from '../../admin/components/ShooterPicker';
import { useRefreshIdentity, useSetStatus } from '../api';
import { SelectField, STATUS_OPTIONS } from './Fields';

type Status = 'member' | 'guest' | 'deceased';

export function StatusForm() {
  const [shooter, setShooter] = useState<ShooterOption | null>(null);
  const [status, setStatus] = useState('');
  const setStatusMutation = useSetStatus();
  const refresh = useRefreshIdentity();
  const request =
    shooter !== null && status !== '' ? { id: shooter.shooter_id, status: status as Status } : null;
  return (
    <div className="flex flex-col gap-3">
      <ShooterPicker label="Shooter" value={shooter} onChange={setShooter} />
      <SelectField label="Status" value={status} onChange={setStatus} options={STATUS_OPTIONS} />
      <Button
        disabled={request === null || setStatusMutation.isPending}
        onClick={() => request && setStatusMutation.mutate(request)}
      >
        Set status
      </Button>
      {setStatusMutation.isError && <AdminError error={setStatusMutation.error} />}
      {setStatusMutation.isSuccess && (
        <JobProgress
          jobId={setStatusMutation.data.job_id}
          label={`Setting status of #${setStatusMutation.variables.id}`}
          onSettled={refresh}
        />
      )}
    </div>
  );
}
