import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { ContactsTab } from './ContactsTab';

describe('ContactsTab', () => {
  it('stacks the rows on a phone: no table, nothing to scroll sideways', async () => {
    stubViewport('mobile');
    renderWithProviders(<ContactsTab />, { role: 'admin' });
    const list = await screen.findByRole('list', { name: 'Emails on file' });
    expect(within(list).getByText('Hadley, Ike')).toBeInTheDocument();
    expect(within(list).getByText('ike.hadley@example.com')).toHaveClass('break-all');
    expect(
      within(list).getByRole('button', { name: 'Edit email for Hadley, Ike' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('lists emails on file and edits one', async () => {
    stubViewport('desktop');
    let body: unknown = null;
    server.use(
      http.put('*/api/admin/shooter-contacts/3', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          shooter_id: 3,
          name: 'Hadley, Ike',
          email: 'ike@example.com',
          source: 'organizer',
          updated_at: '2026-10-02T18:00:00Z',
          last_used_at: null,
          last_used_on: null,
        });
      }),
    );
    const { user } = renderWithProviders(<ContactsTab />, { role: 'admin' });
    const row = (await screen.findByText('Hadley, Ike')).closest('tr') as HTMLElement;
    expect(within(row).getByText('ike.hadley@example.com')).toBeInTheDocument();
    expect(within(row).getByText('Sign-up')).toBeInTheDocument();
    expect(within(row).getByText('Oct 1, 2026')).toBeInTheDocument();
    await user.click(within(row).getByRole('button', { name: 'Edit email for Hadley, Ike' }));
    const sheet = within(screen.getByRole('dialog'));
    await user.clear(sheet.getByLabelText('Email'));
    await user.type(sheet.getByLabelText('Email'), 'ike@example.com');
    await user.click(sheet.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(body).toEqual({ email: 'ike@example.com' }));
  });

  it('removes one after a confirm', async () => {
    stubViewport('desktop');
    let removed = false;
    server.use(
      http.delete('*/api/admin/shooter-contacts/3', () => {
        removed = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderWithProviders(<ContactsTab />, { role: 'admin' });
    await user.click(await screen.findByRole('button', { name: 'Remove email for Hadley, Ike' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(removed).toBe(true));
  });
});
