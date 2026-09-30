import { Card } from '../../../components/ui/Card';
import { ImportHistory } from '../components/ImportHistory';
import { UploadForm } from '../components/UploadForm';

export function ImportsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-medium">Imports</h1>
      <Card title="Upload a workbook">
        <UploadForm />
      </Card>
      <Card title="Import history">
        <ImportHistory />
      </Card>
    </div>
  );
}
