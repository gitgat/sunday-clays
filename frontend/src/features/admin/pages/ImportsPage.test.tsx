import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { importsList } from '../mocks';
import { ImportsPage } from './ImportsPage';

describe('ImportsPage', () => {
  it('shows the upload form and the import history', async () => {
    server.use(http.get('*/api/admin/imports', () => HttpResponse.json(importsList)));
    renderWithProviders(<ImportsPage />, { route: '/admin' });
    expect(screen.getByRole('heading', { level: 1, name: 'Imports' })).toBeInTheDocument();
    expect(screen.getByLabelText('Workbook (.xlsx)')).toBeInTheDocument();
    expect(await screen.findByRole('table', { name: 'Import history' })).toBeInTheDocument();
  });

  it('a viewer session sees the admins-only message', async () => {
    server.use(
      http.get('*/api/admin/imports', () =>
        HttpResponse.json({ error: { code: 'forbidden', message: 'Forbidden' } }, { status: 403 }),
      ),
    );
    renderWithProviders(<ImportsPage />, { route: '/admin' });
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Admins only — sign in with the admin password.',
    );
  });
});
