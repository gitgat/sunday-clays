import { Link, useParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { useImport, useImports } from '../api';
import { AdminError } from '../components/AdminError';
import { ImportPreviewView } from '../components/ImportPreviewView';

export function ImportDetailPage() {
  const { id: idParam = '' } = useParams();
  const id = Number(idParam);
  const preview = useImport(id);
  const imports = useImports();
  const allImports = useRoundTypeLink('/admin');

  if (!Number.isInteger(id) || id <= 0) return <EmptyState title="Import not found" />;
  if (preview.isPending) return <Skeleton className="h-96" />;
  if (preview.isError) {
    return preview.error instanceof ApiError && preview.error.status === 404 ? (
      <EmptyState title="Import not found" />
    ) : (
      <AdminError error={preview.error} />
    );
  }
  // ImportPreview has no status (C5); take it from the list once that has loaded.
  const status = imports.isSuccess ? imports.data.find((i) => i.id === id)?.status : undefined;
  return (
    <div className="flex flex-col gap-3">
      <Link
        to={allImports}
        className="inline-flex min-h-11 items-center self-start text-accent underline-offset-2 hover:underline"
      >
        ← All imports
      </Link>
      <ImportPreviewView preview={preview.data} status={status} />
    </div>
  );
}
