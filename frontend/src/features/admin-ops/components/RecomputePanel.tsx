import { useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Toggle } from '../../../components/ui/Toggle';
import { AdminError } from '../../admin/components/AdminError';
import { JobProgress } from '../../admin/components/JobProgress';
import { useRecompute } from '../api';

/** C6: recompute re-runs the pipeline; recalibrate first deletes app_state.skill_params so s30 refits the model. */
export function RecomputePanel() {
  const [recalibrate, setRecalibrate] = useState(false);
  const recompute = useRecompute();
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-text-muted">
        Re-runs every analytics step (metrics, event weather, skill model, trophies). Recalibrating
        also refits the skill model’s parameters and takes longer.
      </p>
      <Toggle checked={recalibrate} onChange={setRecalibrate} label="Recalibrate skill model" />
      <Button disabled={recompute.isPending} onClick={() => recompute.mutate({ recalibrate })}>
        Recompute analytics
      </Button>
      {recompute.isError && <AdminError error={recompute.error} />}
      {recompute.isSuccess && (
        <JobProgress
          jobId={recompute.data.job_id}
          label={recompute.variables.recalibrate ? 'Recompute with recalibration' : 'Recompute'}
        />
      )}
    </div>
  );
}
