import { Card } from '../../../components/ui/Card';
import { AuditLog } from '../components/AuditLog';
import { DataIssues } from '../components/DataIssues';
import { RecomputePanel } from '../components/RecomputePanel';

export function OpsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-medium">Data & ops</h1>
      <Card title="Data issues">
        <DataIssues />
      </Card>
      <Card title="Recompute analytics">
        <RecomputePanel />
      </Card>
      <Card title="Audit log">
        <AuditLog />
      </Card>
    </div>
  );
}
