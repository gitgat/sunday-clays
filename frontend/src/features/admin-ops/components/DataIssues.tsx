import { Link } from 'react-router';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { AdminError } from '../../admin/components/AdminError';
import { formatDay } from '../../admin/format';
import { useDataIssues } from '../api';
import type { DataIssue } from '../api';
import { AssignAlias } from './AssignAlias';

export type IssueGroup = { code: string; severity: string; items: DataIssue[] };

const severityRank = (s: string) => (s === 'error' ? 0 : s === 'warning' ? 1 : 2);

export function groupIssues(issues: DataIssue[]): IssueGroup[] {
  const byCode = new Map<string, DataIssue[]>();
  for (const issue of issues) byCode.set(issue.code, [...(byCode.get(issue.code) ?? []), issue]);
  return [...byCode.entries()]
    .map(([code, items]) => ({ code, severity: (items[0] as DataIssue).severity, items }))
    .sort(
      (a, b) => severityRank(a.severity) - severityRank(b.severity) || a.code.localeCompare(b.code),
    );
}

const LINK = 'inline-flex min-h-11 items-center text-accent underline-offset-2 hover:underline';

/** An in-app link that keeps the global round-type filter (C10). */
function KeepLink({ path, children }: { path: string; children: string }) {
  return (
    <Link to={useRoundTypeLink(path)} className={LINK}>
      {children}
    </Link>
  );
}

function IssueItem({ issue }: { issue: DataIssue }) {
  const nameKey = typeof issue.details.name_key === 'string' ? issue.details.name_key : null;
  const rawName = typeof issue.details.raw_name === 'string' ? issue.details.raw_name : null;
  return (
    <li className="flex min-w-0 flex-col gap-1 py-2">
      <span className="[overflow-wrap:anywhere]">{issue.message}</span>
      <span className="flex flex-wrap gap-x-3 text-sm">
        {issue.event_date !== null && (
          <KeepLink path={`/events/${issue.event_date}`}>{formatDay(issue.event_date)}</KeepLink>
        )}
        {issue.shooter_id !== null && (
          <KeepLink
            path={`/shooters/${issue.shooter_id}`}
          >{`Shooter #${issue.shooter_id}`}</KeepLink>
        )}
      </span>
      {issue.code === 'station_name_unmatched' && nameKey !== null && (
        <AssignAlias nameKey={nameKey} rawName={rawName ?? nameKey} />
      )}
    </li>
  );
}

export function DataIssues() {
  const issues = useDataIssues();
  if (issues.isPending) return <Skeleton className="h-40" />;
  if (issues.isError) return <AdminError error={issues.error} />;
  if (issues.data.length === 0) return <p className="text-text-muted">No data issues.</p>;
  return (
    <div className="flex flex-col gap-2">
      {groupIssues(issues.data).map((group) => (
        <details
          key={group.code}
          open={group.severity !== 'info'}
          className="min-w-0 rounded-card border border-outline-variant p-3"
        >
          <summary className="flex min-h-11 cursor-pointer items-center [overflow-wrap:anywhere]">{`${group.code} (${group.items.length}) · ${group.severity}`}</summary>
          <ul className="flex flex-col divide-y divide-outline-variant">
            {group.items.map((issue) => (
              <IssueItem key={issue.id} issue={issue} />
            ))}
          </ul>
        </details>
      ))}
    </div>
  );
}
