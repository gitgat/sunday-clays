import { useState } from 'react';
import { Button } from '../../../components/ui/Button';
import type { ShooterOption } from '../../admin/api';
import { AdminError } from '../../admin/components/AdminError';
import { JobProgress } from '../../admin/components/JobProgress';
import { ShooterPicker } from '../../admin/components/ShooterPicker';
import { useRefreshIdentity, useRenameShooter } from '../api';
import { TextField } from './Fields';

export function RenameForm() {
  const [shooter, setShooter] = useState<ShooterOption | null>(null);
  const [name, setName] = useState('');
  const rename = useRenameShooter();
  const refresh = useRefreshIdentity();
  const request =
    shooter !== null && name.trim() !== ''
      ? { id: shooter.shooter_id, displayName: name.trim() }
      : null;
  return (
    <div className="flex flex-col gap-3">
      <ShooterPicker label="Shooter" value={shooter} onChange={setShooter} />
      <TextField label="New display name" value={name} onChange={setName} />
      <Button
        disabled={request === null || rename.isPending}
        onClick={() => request && rename.mutate(request)}
      >
        Rename
      </Button>
      {rename.isError && <AdminError error={rename.error} />}
      {rename.isSuccess && (
        <JobProgress
          jobId={rename.data.job_id}
          label={`Renaming #${rename.variables.id}`}
          onSettled={refresh}
        />
      )}
    </div>
  );
}
