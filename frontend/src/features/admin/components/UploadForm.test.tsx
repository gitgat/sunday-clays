import { fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Route, Routes, useParams } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { scoresPreview } from '../mocks';
import { UploadForm } from './UploadForm';

function PreviewProbe() {
  const { id } = useParams();
  return <p>{`preview ${String(id)}`}</p>;
}

function renderUpload(route = '/admin') {
  return renderWithProviders(
    <Routes>
      <Route path="/admin" element={<UploadForm />} />
      <Route path="/admin/imports/:id" element={<PreviewProbe />} />
    </Routes>,
    { route },
  );
}

const workbook = () =>
  new File(['PK'], 'scores_2026-10-04.xlsx', {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });

describe('UploadForm', () => {
  it('uploads the chosen workbook and opens its preview', async () => {
    let uploads = 0;
    server.use(
      http.post('*/api/admin/imports', () => {
        uploads += 1;
        return HttpResponse.json(scoresPreview);
      }),
    );
    const user = userEvent.setup();
    const { router } = renderUpload('/admin?rt=super_sporting');
    const submit = screen.getByRole('button', { name: 'Upload and preview' });
    expect(submit).toBeDisabled();
    await user.upload(screen.getByLabelText('Workbook (.xlsx)'), workbook());
    await user.click(submit);
    expect(await screen.findByText('preview 4')).toBeInTheDocument();
    expect(uploads).toBe(1);
    // The global round-type filter survives in-app navigation (C10).
    expect(router.state.location.search).toBe('?rt=super_sporting');
  });

  it('shows the upload in progress and blocks a second submit until it answers', async () => {
    let uploads = 0;
    let answer: () => void = () => undefined;
    const answered = new Promise<void>((resolve) => {
      answer = resolve;
    });
    server.use(
      http.post('*/api/admin/imports', async () => {
        uploads += 1;
        await answered;
        return HttpResponse.json(scoresPreview);
      }),
    );
    const user = userEvent.setup();
    renderUpload();
    await user.upload(screen.getByLabelText('Workbook (.xlsx)'), workbook());
    await user.click(screen.getByRole('button', { name: 'Upload and preview' }));
    expect(await screen.findByRole('button', { name: 'Uploading…' })).toBeDisabled();
    answer();
    expect(await screen.findByText('preview 4')).toBeInTheDocument();
    expect(uploads).toBe(1);
  });

  it('upload of an unreadable file shows the server message', async () => {
    server.use(
      http.post('*/api/admin/imports', () =>
        HttpResponse.json(
          {
            error: {
              code: 'unreadable_file',
              message: 'This file could not be read as an Excel workbook',
            },
          },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderUpload();
    await user.upload(screen.getByLabelText('Workbook (.xlsx)'), workbook());
    await user.click(screen.getByRole('button', { name: 'Upload and preview' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This file could not be read as an Excel workbook',
    );
    expect(screen.getByRole('button', { name: 'Upload and preview' })).toBeEnabled();
  });

  it('clearing the chosen file disables upload, and a keyboard submit without a file sends nothing', async () => {
    let uploads = 0;
    server.use(
      http.post('*/api/admin/imports', () => {
        uploads += 1;
        return HttpResponse.json(scoresPreview);
      }),
    );
    const user = userEvent.setup();
    renderUpload();
    const input = screen.getByLabelText('Workbook (.xlsx)');
    await user.upload(input, workbook());
    expect(screen.getByRole('button', { name: 'Upload and preview' })).toBeEnabled();
    await user.upload(input, []);
    const submit = screen.getByRole('button', { name: 'Upload and preview' });
    expect(submit).toBeDisabled();
    const form = submit.closest('form');
    if (form === null) throw new Error('upload form not found');
    fireEvent.submit(form);
    expect(uploads).toBe(0);
  });
});
