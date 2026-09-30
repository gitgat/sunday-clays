import { Card } from '../../../components/ui/Card';
import { DuplicatesQueue } from '../components/DuplicatesQueue';
import { RenameForm } from '../components/RenameForm';
import { RuleCreateForm } from '../components/RuleCreateForm';
import { RulesList } from '../components/RulesList';
import { StatusForm } from '../components/StatusForm';

export function IdentityPage() {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <h1 className="text-2xl font-medium">Identity & rules</h1>
      <Card title="Possible duplicates">
        <DuplicatesQueue />
      </Card>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <Card title="Rename a shooter">
          <RenameForm />
        </Card>
        <Card title="Set a shooter's status">
          <StatusForm />
        </Card>
      </div>
      <Card title="Rules">
        <RulesList />
      </Card>
      <Card title="New rule">
        <RuleCreateForm />
      </Card>
    </div>
  );
}
