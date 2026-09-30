import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { doneJob } from '../../admin/mocks';
import { RecomputePanel } from './RecomputePanel';

const bodies: unknown[] = [];

describe('RecomputePanel', () => {
  beforeEach(() => {
    bodies.length = 0;
    server.use(
      http.post('*/api/admin/recompute', async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ job_id: 81 + bodies.length });
      }),
      http.get('*/api/admin/jobs/:id', ({ params }) =>
        HttpResponse.json({ ...doneJob, id: Number(params.id) }),
      ),
    );
  });

  it('recomputes without recalibrating by default', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RecomputePanel />);
    await user.click(screen.getByRole('button', { name: 'Recompute analytics' }));
    expect(await screen.findByText('Recompute: Done')).toBeInTheDocument();
    expect(bodies).toEqual([{ recalibrate: false }]);
  });

  it('sends recalibrate: true when the toggle is on', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RecomputePanel />);
    await user.click(screen.getByRole('switch', { name: 'Recalibrate skill model' }));
    await user.click(screen.getByRole('button', { name: 'Recompute analytics' }));
    expect(await screen.findByText('Recompute with recalibration: Done')).toBeInTheDocument();
    expect(bodies).toEqual([{ recalibrate: true }]);
  });

  it('shows a rejected recompute', async () => {
    server.use(
      http.post('*/api/admin/recompute', () =>
        HttpResponse.json({ error: { code: 'forbidden', message: 'Forbidden' } }, { status: 403 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecomputePanel />);
    await user.click(screen.getByRole('button', { name: 'Recompute analytics' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Admins only — sign in with the admin password.',
    );
  });
});
