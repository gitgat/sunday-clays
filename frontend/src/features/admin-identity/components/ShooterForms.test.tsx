import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { UserEvent } from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { doneJob, shooterMatches } from '../../admin/mocks';
import { RenameForm } from './RenameForm';
import { StatusForm } from './StatusForm';

const bodies: unknown[] = [];

async function pickHadley(user: UserEvent) {
  await user.type(screen.getByRole('searchbox', { name: 'Shooter' }), 'cr');
  await user.click(await screen.findByRole('button', { name: 'Hadley, Ike · 267 rounds' }));
}

describe('shooter forms', () => {
  beforeEach(() => {
    bodies.length = 0;
    server.use(
      http.get('*/api/shooters', () => HttpResponse.json(shooterMatches)),
      http.post('*/api/admin/shooters/:id/rename', async ({ request, params }) => {
        bodies.push({ id: params.id, ...((await request.json()) as object) });
        return HttpResponse.json({ rule_id: 5, job_id: 61 });
      }),
      http.post('*/api/admin/shooters/:id/status', async ({ request, params }) => {
        bodies.push({ id: params.id, ...((await request.json()) as object) });
        return HttpResponse.json({ rule_id: 6, job_id: 62 });
      }),
      http.get('*/api/admin/jobs/:id', ({ params }) =>
        HttpResponse.json({ ...doneJob, id: Number(params.id) }),
      ),
    );
  });

  it('renames a shooter once a shooter and a name are given', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RenameForm />);
    const submit = screen.getByRole('button', { name: 'Rename' });
    expect(submit).toBeDisabled();
    await pickHadley(user);
    await user.type(screen.getByLabelText('New display name'), ' Hadley, Clint ');
    await user.click(submit);
    expect(await screen.findByText('Renaming #3: Done')).toBeInTheDocument();
    expect(bodies).toEqual([{ id: '3', display_name: 'Hadley, Clint' }]);
  });

  it('sets a status, including the memorial status', async () => {
    const user = userEvent.setup();
    renderWithProviders(<StatusForm />);
    await pickHadley(user);
    expect(screen.getByRole('button', { name: 'Set status' })).toBeDisabled();
    await user.selectOptions(screen.getByLabelText('Status'), 'deceased');
    await user.click(screen.getByRole('button', { name: 'Set status' }));
    expect(await screen.findByText('Setting status of #3: Done')).toBeInTheDocument();
    expect(bodies).toEqual([{ id: '3', status: 'deceased' }]);
  });

  it('shows a rejected rename next to the form', async () => {
    server.use(
      http.post('*/api/admin/shooters/:id/rename', () =>
        HttpResponse.json(
          { error: { code: 'invalid', message: 'Display name is too long' } },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RenameForm />);
    await pickHadley(user);
    await user.type(screen.getByLabelText('New display name'), 'x');
    await user.click(screen.getByRole('button', { name: 'Rename' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Display name is too long');
  });

  it('shows a rejected status change next to the form', async () => {
    server.use(
      http.post('*/api/admin/shooters/:id/status', () =>
        HttpResponse.json(
          { error: { code: 'not_found', message: 'No such shooter' } },
          { status: 404 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<StatusForm />);
    await pickHadley(user);
    await user.selectOptions(screen.getByLabelText('Status'), 'guest');
    await user.click(screen.getByRole('button', { name: 'Set status' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No such shooter');
  });

  it.each([
    ['rename', <RenameForm key="r" />, 'Rename', 'Renaming #3: Done'],
    ['status', <StatusForm key="s" />, 'Set status', 'Setting status of #3: Done'],
  ])(
    'refreshes the rules and duplicates lists once the %s rebuild settles',
    async (kind, form, button, done) => {
      const user = userEvent.setup();
      const { queryClient } = renderWithProviders(form);
      const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
      await pickHadley(user);
      if (kind === 'rename') await user.type(screen.getByLabelText('New display name'), 'X');
      else await user.selectOptions(screen.getByLabelText('Status'), 'guest');
      await user.click(screen.getByRole('button', { name: button }));
      expect(await screen.findByText(done)).toBeInTheDocument();
      await vi.waitFor(() => {
        expect(invalidate).toHaveBeenCalledWith({ queryKey: ['/api/admin/rules'] });
        expect(invalidate).toHaveBeenCalledWith({ queryKey: ['/api/admin/possible-duplicates'] });
      });
    },
  );
});
