import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { importsList, stalePreview } from '../mocks';
import { ImportDetailPage } from './ImportDetailPage';

function renderDetail(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/imports/:id" element={<ImportDetailPage />} />
    </Routes>,
    { route },
  );
}

const fail = (status: number) => () =>
  HttpResponse.json(
    { error: { code: status === 404 ? 'not_found' : 'internal', message: `HTTP ${status}` } },
    { status },
  );

describe('ImportDetailPage', () => {
  it('shows the preview with the status from the import list', async () => {
    server.use(
      http.get('*/api/admin/imports/:id', () => HttpResponse.json(stalePreview)),
      http.get('*/api/admin/imports', () => HttpResponse.json(importsList)),
    );
    renderDetail('/admin/imports/3');
    expect(await screen.findByRole('heading', { level: 1, name: 'Import #3' })).toBeInTheDocument();
    expect(
      await screen.findByText('scores_old.xlsx · Scores workbook · Pending'),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '← All imports' })).toHaveAttribute('href', '/admin');
  });

  it('an import missing from the list has an unknown status', async () => {
    server.use(
      http.get('*/api/admin/imports/:id', () => HttpResponse.json(stalePreview)),
      http.get('*/api/admin/imports', () => HttpResponse.json(importsList.slice(0, 2))),
    );
    renderDetail('/admin/imports/3');
    expect(await screen.findByText('scores_old.xlsx · Scores workbook · …')).toBeInTheDocument();
  });

  it('a failed import list leaves the status unknown', async () => {
    server.use(
      http.get('*/api/admin/imports/:id', () => HttpResponse.json(stalePreview)),
      http.get('*/api/admin/imports', fail(500)),
    );
    renderDetail('/admin/imports/3');
    expect(await screen.findByText('scores_old.xlsx · Scores workbook · …')).toBeInTheDocument();
  });

  it('an unknown import says not found', async () => {
    server.use(
      http.get('*/api/admin/imports/:id', fail(404)),
      http.get('*/api/admin/imports', () => HttpResponse.json([])),
    );
    renderDetail('/admin/imports/99');
    expect(await screen.findByText('Import not found')).toBeInTheDocument();
  });

  it('a malformed id says not found without calling the API', async () => {
    let previews = 0;
    server.use(
      http.get('*/api/admin/imports/:id', () => {
        previews += 1;
        return HttpResponse.json(stalePreview);
      }),
      http.get('*/api/admin/imports', () => HttpResponse.json([])),
    );
    renderDetail('/admin/imports/abc');
    expect(await screen.findByText('Import not found')).toBeInTheDocument();
    expect(previews).toBe(0);
  });

  it('other errors show the server message', async () => {
    server.use(
      http.get('*/api/admin/imports/:id', fail(500)),
      http.get('*/api/admin/imports', () => HttpResponse.json([])),
    );
    renderDetail('/admin/imports/3');
    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 500');
  });
});
