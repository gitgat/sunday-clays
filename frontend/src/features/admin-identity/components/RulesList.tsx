import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Skeleton } from '../../../components/ui/Skeleton';
import { AdminError } from '../../admin/components/AdminError';
import { JobProgress } from '../../admin/components/JobProgress';
import { formatTimestamp } from '../../admin/format';
import { useDeactivateRule, useRules } from '../api';
import { RULE_LABELS, RULE_TYPES, ruleSummary } from '../rules';
import type { RuleType } from '../rules';

const typeLabel = (t: string) =>
  (RULE_TYPES as readonly string[]).includes(t) ? RULE_LABELS[t as RuleType] : t;

const CELL = 'py-2 pr-2 max-sm:py-0';

export function RulesList() {
  const rules = useRules();
  const deactivate = useDeactivateRule();
  const qc = useQueryClient();
  const [job, setJob] = useState<{ ruleId: number; jobId: number } | null>(null);
  const refresh = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ['/api/admin/rules'] });
  }, [qc]);

  if (rules.isPending) return <Skeleton className="h-40" />;
  if (rules.isError) return <AdminError error={rules.error} />;
  if (rules.data.length === 0) return <p className="text-text-muted">No rules yet.</p>;

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {job !== null && (
        <JobProgress
          jobId={job.jobId}
          label={`Deactivating rule #${job.ruleId}`}
          onSettled={refresh}
        />
      )}
      {deactivate.isError && <AdminError error={deactivate.error} />}
      {/*
        Explicit roles: below `sm` the table, rows and cells are stacked cards (display: block/flex), which would
        otherwise drop the table semantics. Each card reads: type, #id, details, note, created, state (the # and
        details cells are full-width rows, so the id sits alone), then the action on its own line.
      */}
      <table aria-label="Rules" role="table" className="w-full text-sm max-sm:block">
        <thead role="rowgroup" className="text-left text-text-muted max-sm:sr-only">
          <tr role="row">
            {['#', 'Type', 'Details', 'Note', 'Created', 'State', 'Action'].map((h) => (
              <th key={h} role="columnheader" scope="col" className="py-2 pr-2">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody role="rowgroup" className="max-sm:flex max-sm:flex-col">
          {rules.data.map((rule) => (
            <tr
              key={rule.id}
              role="row"
              className="border-t border-outline-variant max-sm:flex max-sm:flex-wrap max-sm:items-center max-sm:gap-x-3 max-sm:py-2"
            >
              <td role="cell" className={`${CELL} tabular-nums`}>{`#${rule.id}`}</td>
              <td
                role="cell"
                className={`${CELL} max-sm:order-first max-sm:basis-full max-sm:font-medium`}
              >
                {typeLabel(rule.rule_type)}
              </td>
              <td
                role="cell"
                className={`${CELL} min-w-0 [overflow-wrap:anywhere] max-sm:basis-full`}
              >
                {ruleSummary(rule.payload)}
              </td>
              <td
                role="cell"
                className={`${CELL} min-w-0 [overflow-wrap:anywhere] max-sm:basis-full max-sm:empty:hidden`}
              >
                {rule.note ?? ''}
              </td>
              <td role="cell" className={CELL}>
                {formatTimestamp(rule.created_at)}
              </td>
              <td role="cell" className={CELL}>
                {rule.active ? 'Active' : 'Inactive'}
              </td>
              <td role="cell" className="py-2 max-sm:basis-full max-sm:py-0 max-sm:empty:hidden">
                {rule.active && (
                  <Button
                    variant="tonal"
                    aria-label={`Deactivate rule #${rule.id}`}
                    disabled={deactivate.isPending}
                    onClick={() =>
                      deactivate.mutate(rule.id, {
                        onSuccess: (r) => setJob({ ruleId: rule.id, jobId: r.job_id }),
                      })
                    }
                  >
                    Deactivate
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
