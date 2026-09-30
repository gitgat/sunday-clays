import { useQueryClient } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../../../components/ui/Button';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import { useUploadImport } from '../api';
import { AdminError } from './AdminError';

export function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const upload = useUploadImport();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const href = useRoundTypeHref();
  const inputId = useId();

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (file === null) return;
        upload.mutate(file, {
          onSuccess: (preview) => {
            qc.setQueryData(['/api/admin/imports/{id}', preview.import_id], preview);
            void qc.invalidateQueries({ queryKey: ['/api/admin/imports'] });
            void navigate(href(`/admin/imports/${preview.import_id}`));
          },
        });
      }}
    >
      <label htmlFor={inputId} className="text-sm">
        Workbook (.xlsx)
      </label>
      <input
        id={inputId}
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className="min-h-11"
        onChange={(e) => setFile(e.currentTarget.files?.item(0) ?? null)}
      />
      <p className="text-xs text-text-muted">
        The kind (scores or stations) is detected from the workbook itself.
      </p>
      <Button type="submit" disabled={file === null || upload.isPending}>
        {upload.isPending ? 'Uploading…' : 'Upload and preview'}
      </Button>
      {upload.isError && <AdminError error={upload.error} />}
    </form>
  );
}
