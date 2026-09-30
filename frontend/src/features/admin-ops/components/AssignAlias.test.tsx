import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { UserEvent } from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { doneJob, shooterMatches } from '../../admin/mocks';
import { AssignAlias } from './AssignAlias';

const assigned: unknown[] = [];

async function chooseHadley(user: UserEvent) {
  await user.click(screen.getByRole('button', { name: 'Assign to shooter' }));
  await user.type(screen.getByRole('searchbox', { name: 'Shooter for “Hadley, Dik”' }), 'cr');
  await user.click(await screen.findByRole('button', { name: 'Hadley, Ike · 267 rounds' }));
}

describe('AssignAlias', () => {
  beforeEach(() => {
    assigned.length = 0;
    server.use(
      http.get('*/api/shooters', () => HttpResponse.json(shooterMatches)),
      http.post('*/api/admin/shooters/:id/aliases', async ({ request, params }) => {
        assigned.push({ id: params.id, ...((await request.json()) as object) });
        return HttpResponse.json({ rule_id: 4, job_id: 82 });
      }),
      http.get('*/api/admin/jobs/:id', ({ params }) =>
        HttpResponse.json({ ...doneJob, id: Number(params.id) }),
      ),
    );
  });

  it('assigns the unmatched name key to the chosen shooter and follows the rebuild', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AssignAlias nameKey="hadley dik" rawName="Hadley, Dik" />);
    await chooseHadley(user);
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    expect(await screen.findByText('Alias hadley dik → #3: Done')).toBeInTheDocument();
    expect(assigned).toEqual([{ id: '3', name_key: 'hadley dik' }]);
  });

  it('cancel closes the picker without a request', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AssignAlias nameKey="hadley dik" rawName="Hadley, Dik" />);
    await user.click(screen.getByRole('button', { name: 'Assign to shooter' }));
    expect(screen.getByRole('button', { name: 'Assign' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('button', { name: 'Assign to shooter' })).toBeInTheDocument();
    expect(assigned).toEqual([]);
  });

  it('shows a rejected assignment', async () => {
    server.use(
      http.post('*/api/admin/shooters/:id/aliases', () =>
        HttpResponse.json(
          { error: { code: 'conflict', message: 'hadley dik is already an alias' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<AssignAlias nameKey="hadley dik" rawName="Hadley, Dik" />);
    await chooseHadley(user);
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('hadley dik is already an alias');
  });

  it('disables Assign once the assignment succeeded', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AssignAlias nameKey="hadley dik" rawName="Hadley, Dik" />);
    await chooseHadley(user);
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    await screen.findByText('Alias hadley dik → #3: Done');
    expect(screen.getByRole('button', { name: 'Assign' })).toBeDisabled();
  });

  it('cancel forgets the chosen shooter and the previous result', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AssignAlias nameKey="hadley dik" rawName="Hadley, Dik" />);
    await chooseHadley(user);
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    await screen.findByText('Alias hadley dik → #3: Done');
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    await user.click(screen.getByRole('button', { name: 'Assign to shooter' }));
    expect(screen.queryByText('Alias hadley dik → #3: Done')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Assign' })).toBeDisabled();
  });
});
