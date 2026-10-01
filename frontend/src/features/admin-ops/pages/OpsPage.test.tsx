import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { doneJob } from '../../admin/mocks';
import { auditEntries, dataIssues } from '../mocks';
import { OpsPage } from './OpsPage';

describe('OpsPage', () => {
  it('shows data issues, the recompute panel, fist bumps and the audit log', async () => {
    server.use(
      http.get('*/api/admin/data-issues', () => HttpResponse.json(dataIssues)),
      http.get('*/api/admin/audit', () => HttpResponse.json(auditEntries)),
    );
    renderWithProviders(<OpsPage />, { route: '/admin/ops' });
    expect(screen.getByRole('heading', { level: 1, name: 'Data & ops' })).toBeInTheDocument();
    expect(await screen.findByText('station_score_mismatch (1) · warning')).toBeInTheDocument();
    expect(await screen.findByRole('table', { name: 'Audit log' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Recompute analytics' })).toBeInTheDocument();
    const bumps = screen.getByRole('region', { name: 'Fist bumps' });
    expect(await within(bumps).findByRole('list', { name: 'Bumped posts' })).toBeInTheDocument();
  });

  it('recomputing refreshes the audit log with the new entry', async () => {
    const entries = [...auditEntries];
    server.use(
      http.get('*/api/admin/data-issues', () => HttpResponse.json(dataIssues)),
      http.get('*/api/admin/audit', () => HttpResponse.json(entries)),
      http.post('*/api/admin/recompute', () => {
        entries.push({
          id: 3,
          at: '2026-09-27T18:07:00Z',
          ip: null,
          role: 'admin',
          action: 'ops.recompute',
          details: { recalibrate: false },
        });
        return HttpResponse.json({ job_id: 81 });
      }),
      http.get('*/api/admin/jobs/:id', ({ params }) =>
        HttpResponse.json({ ...doneJob, id: Number(params.id) }),
      ),
    );
    const { user } = renderWithProviders(<OpsPage />, { route: '/admin/ops' });
    const log = await screen.findByRole('table', { name: 'Audit log' });
    expect(within(log).getAllByRole('row')).toHaveLength(3);
    await user.click(screen.getByRole('button', { name: 'Recompute analytics' }));
    expect(await within(log).findByText('ops.recompute')).toBeInTheDocument();
  });

  it('a viewer session sees the admins-only message', async () => {
    const forbidden = () =>
      HttpResponse.json({ error: { code: 'forbidden', message: 'Forbidden' } }, { status: 403 });
    server.use(
      http.get('*/api/admin/data-issues', forbidden),
      http.get('*/api/admin/audit', forbidden),
    );
    renderWithProviders(<OpsPage />, { route: '/admin/ops' });
    // Two independent queries fail; wait until both messages are shown.
    await waitFor(() =>
      expect(screen.getAllByText('Admins only — sign in with the admin password.')).toHaveLength(2),
    );
  });
});
