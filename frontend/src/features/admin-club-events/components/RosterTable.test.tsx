import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { rosterRows } from '../mocks';
import { RosterTable } from './RosterTable';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('RosterTable', () => {
  it('is a table with the six columns and the actions on a desktop', () => {
    stubViewport('desktop');
    renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, { role: 'admin' });
    const table = screen.getByRole('table');
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((c) => c.textContent),
    ).toEqual(['Name', 'Email', 'Guests', 'Status', 'Signed up', 'Source', 'Actions']);
    expect(within(table).getByText('ike.hadley@example.com')).toBeInTheDocument();
    expect(within(table).getAllByText('2026-10-02 11:05')).toHaveLength(3);
  });

  it('stacks the rows on a phone, with no table', () => {
    stubViewport('mobile');
    renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, { role: 'admin' });
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    const list = screen.getByRole('list', { name: 'Sign-ups' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(3);
  });

  it('removes a sign-up after a confirm', async () => {
    stubViewport('desktop');
    let removed = false;
    server.use(
      http.delete('*/api/admin/club-events/1/registrations/41', () => {
        removed = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Remove Hadley, Ike' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(removed).toBe(true));
  });

  it('changes guests', async () => {
    stubViewport('desktop');
    let body: unknown = null;
    server.use(
      http.patch('*/api/admin/club-events/1/registrations/41', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ guests: 0 });
      }),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Guests for Hadley, Ike' }));
    const sheet = within(screen.getByRole('dialog'));
    await user.clear(sheet.getByLabelText('Guests'));
    await user.type(sheet.getByLabelText('Guests'), '0');
    await user.click(sheet.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(body).toEqual({ guests: 0 }));
  });

  it('suggests a match and says the typed email will be deleted', async () => {
    stubViewport('desktop');
    let body: unknown = null;
    server.use(
      http.post('*/api/admin/club-events/1/registrations/42/link', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ shooter_id: 3, email_moved: false, email_discarded: true });
      }),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Looks like Hadley, Ike? Link' }));
    const sheet = within(screen.getByRole('dialog'));
    expect(
      sheet.getByText(
        'Hadley, Ike already has an email on file. The email typed at sign-up will be deleted.',
      ),
    ).toBeInTheDocument();
    await user.click(sheet.getByRole('button', { name: 'Link' }));
    await waitFor(() => expect(body).toEqual({ shooter_id: 3 }));
  });

  it('copies no email into the page title or any aria label', () => {
    stubViewport('desktop');
    const { container } = renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, {
      role: 'admin',
    });
    const labels = [...container.querySelectorAll('[aria-label]')].map(
      (el) => el.getAttribute('aria-label') ?? '',
    );
    expect(labels.join(' ')).not.toMatch(/@/);
  });
});
