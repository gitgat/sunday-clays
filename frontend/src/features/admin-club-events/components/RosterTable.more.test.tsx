import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { shooterMatches } from '../../admin/mocks';
import { rosterRows } from '../mocks';
import { RosterTable } from './RosterTable';

const error = (code: string, message: string, status = 409) =>
  HttpResponse.json({ error: { code, message } }, { status });
const locked = rosterRows.map((r) => (r.id === 41 ? { ...r, cancel_fail_count: 1 } : r));
const typed = rosterRows.map((r) => (r.id === 42 ? { ...r, suggested_shooter: null } : r));

describe('RosterTable, more', () => {
  it('resets the cancel lock', async () => {
    stubViewport('desktop');
    let reset = false;
    server.use(
      http.post('*/api/admin/club-events/1/registrations/41/reset-cancel-limit', () => {
        reset = true;
        return HttpResponse.json({ cleared: 1 });
      }),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={locked} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Reset cancel limit for Hadley, Ike' }));
    await waitFor(() => expect(reset).toBe(true));
  });

  it('keeps the list when a remove is refused, and Keep it closes the dialog', async () => {
    stubViewport('mobile');
    server.use(
      http.delete('*/api/admin/club-events/1/registrations/41', () =>
        error('not_active', 'That sign-up is already off the list.'),
      ),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Remove Hadley, Ike' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'That sign-up is already off the list.',
    );
    await user.click(screen.getByRole('button', { name: 'Keep it' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('shows why guests were refused', async () => {
    stubViewport('desktop');
    server.use(
      http.patch('*/api/admin/club-events/1/registrations/41', () =>
        error('guests_over_limit', 'That is more guests than this club event allows.'),
      ),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Guests for Hadley, Ike' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'That is more guests than this club event allows.',
    );
  });

  it('links a typed sign-up to a picked shooter and says the email moved', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/shooters', () => HttpResponse.json(shooterMatches)),
      http.post('*/api/admin/club-events/1/registrations/42/link', () =>
        HttpResponse.json({ shooter_id: 3, email_moved: true, email_discarded: false }),
      ),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={typed} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Link Ike Hadly' }));
    const sheet = within(screen.getByRole('dialog'));
    expect(sheet.getByRole('button', { name: 'Link' })).toBeDisabled();
    await user.type(sheet.getByRole('searchbox', { name: 'Shooter' }), 'ha');
    await user.click(await sheet.findByRole('button', { name: /Hadley, Ike/ }));
    expect(
      sheet.getByText(
        'If Hadley, Ike already has an email on file, the email typed at sign-up will be deleted.',
      ),
    ).toBeInTheDocument();
    await user.click(sheet.getByRole('button', { name: 'Change' }));
    await user.type(sheet.getByRole('searchbox', { name: 'Shooter' }), 'ha');
    await user.click(await sheet.findByRole('button', { name: /Hadley, Ike/ }));
    await user.click(sheet.getByRole('button', { name: 'Link' }));
    expect(
      await screen.findByText(
        'Linked. The email typed at sign-up is now on file for this shooter.',
      ),
    ).toBeInTheDocument();
  });

  it('says plainly when nothing moved, and when the typed email was deleted', async () => {
    stubViewport('desktop');
    let kept = false;
    server.use(
      http.post('*/api/admin/club-events/1/registrations/42/link', () =>
        kept
          ? HttpResponse.json({ shooter_id: 3, email_moved: false, email_discarded: true })
          : HttpResponse.json({ shooter_id: 3, email_moved: false, email_discarded: false }),
      ),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Looks like Hadley, Ike? Link' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Link' }));
    expect(await screen.findByText('Linked.')).toBeInTheDocument();
    kept = true;
    await user.click(screen.getByRole('button', { name: 'Looks like Hadley, Ike? Link' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Link' }));
    expect(
      await screen.findByText(
        'Linked. The email typed at sign-up was deleted; the email on file stays.',
      ),
    ).toBeInTheDocument();
  });

  it('shows a refused link next to the button', async () => {
    stubViewport('desktop');
    server.use(
      http.post('*/api/admin/club-events/1/registrations/42/link', () =>
        error('already_registered', 'That shooter is already on this list.'),
      ),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Looks like Hadley, Ike? Link' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Link' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'That shooter is already on this list.',
    );
  });

  it('shows no reset button when nothing failed', () => {
    stubViewport('desktop');
    renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, { role: 'admin' });
    expect(screen.queryByRole('button', { name: /Reset cancel limit/ })).not.toBeInTheDocument();
  });

  it('shows why a reset was refused', async () => {
    stubViewport('desktop');
    server.use(
      http.post('*/api/admin/club-events/1/registrations/41/reset-cancel-limit', () =>
        error('not_active', 'That sign-up is not active.'),
      ),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={locked} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Reset cancel limit for Hadley, Ike' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('That sign-up is not active.');
  });

  it('offers the match hint only on going and waitlist rows', () => {
    stubViewport('desktop');
    const cancelled = rosterRows.map((r) =>
      r.id === 43
        ? { ...r, suggested_shooter: { id: 3, name: 'Hadley, Ike', has_email: false } }
        : r,
    );
    renderWithProviders(<RosterTable eventId={1} rows={cancelled} />, { role: 'admin' });
    expect(screen.getAllByRole('button', { name: 'Looks like Hadley, Ike? Link' })).toHaveLength(1);
  });

  it('announces the link result as a status and clears it on the next action', async () => {
    stubViewport('desktop');
    server.use(
      http.post('*/api/admin/club-events/1/registrations/42/link', () =>
        HttpResponse.json({ shooter_id: 3, email_moved: false, email_discarded: false }),
      ),
    );
    const { user } = renderWithProviders(<RosterTable eventId={1} rows={rosterRows} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Looks like Hadley, Ike? Link' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Link' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Linked.');
    await user.click(screen.getByRole('button', { name: 'Remove Hadley, Ike' }));
    expect(screen.queryByText('Linked.')).not.toBeInTheDocument();
  });
});
