import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { shooterMatches } from '../../admin/mocks';
import { contacts } from '../mocks';
import { ContactsTab } from './ContactsTab';

const refused = (code: string, message: string, status: number) =>
  HttpResponse.json({ error: { code, message } }, { status });

describe('ContactsTab, more', () => {
  it('shows an unknown source as is and a missing last-used date as a dash', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/admin/shooter-contacts', () =>
        HttpResponse.json([{ ...contacts[0], source: 'import', last_used_on: null }]),
      ),
    );
    renderWithProviders(<ContactsTab />, { role: 'admin' });
    const row = (await screen.findByText('Hadley, Ike')).closest('tr') as HTMLElement;
    expect(within(row).getByText('import')).toBeInTheDocument();
    expect(within(row).getByText('—')).toBeInTheDocument();
  });

  it('adds an email for a picked shooter', async () => {
    stubViewport('mobile');
    let body: unknown = null;
    server.use(
      http.get('*/api/shooters', () => HttpResponse.json(shooterMatches)),
      http.put('*/api/admin/shooter-contacts/3', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(contacts[0]);
      }),
    );
    const { user } = renderWithProviders(<ContactsTab />, { role: 'admin' });
    await user.click(await screen.findByRole('button', { name: 'Add email' }));
    const sheet = within(screen.getByRole('dialog'));
    expect(sheet.getByRole('button', { name: 'Save' })).toBeDisabled();
    await user.type(sheet.getByRole('searchbox', { name: 'Shooter' }), 'ha');
    await user.click(await sheet.findByRole('button', { name: /Hadley, Ike/ }));
    await user.type(sheet.getByLabelText('Email'), 'ike@example.com');
    await user.click(sheet.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(body).toEqual({ email: 'ike@example.com' }));
  });

  it('shows why an email was refused, for a merged-away shooter too', async () => {
    stubViewport('desktop');
    server.use(
      http.put('*/api/admin/shooter-contacts/3', () =>
        refused('shooter_not_found', 'That shooter was not found.', 404),
      ),
    );
    const { user } = renderWithProviders(<ContactsTab />, { role: 'admin' });
    await user.click(await screen.findByRole('button', { name: 'Edit email for Hadley, Ike' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('That shooter was not found.');
  });

  it('shows why a removal was refused, and Keep it closes the dialog', async () => {
    stubViewport('desktop');
    server.use(
      http.delete('*/api/admin/shooter-contacts/3', () =>
        refused('not_found', 'No email on file.', 404),
      ),
    );
    const { user } = renderWithProviders(<ContactsTab />, { role: 'admin' });
    await user.click(await screen.findByRole('button', { name: 'Remove email for Hadley, Ike' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No email on file.');
    await user.click(screen.getByRole('button', { name: 'Keep it' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('does nothing when the form is sent with no shooter picked', async () => {
    stubViewport('desktop');
    let sent = false;
    server.use(
      http.put('*/api/admin/shooter-contacts/:id', () => {
        sent = true;
        return HttpResponse.json(contacts[0]);
      }),
    );
    const { user } = renderWithProviders(<ContactsTab />, { role: 'admin' });
    await user.click(await screen.findByRole('button', { name: 'Add email' }));
    const sheet = within(screen.getByRole('dialog'));
    await user.type(sheet.getByLabelText('Email'), 'x@example.com');
    fireEvent.submit(sheet.getByLabelText('Email').closest('form') as HTMLFormElement);
    expect(sent).toBe(false);
  });
});
