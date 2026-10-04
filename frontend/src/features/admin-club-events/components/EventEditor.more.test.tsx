import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { adminEvent } from '../mocks';
import { EventEditor } from './EventEditor';

afterEach(() => {
  vi.restoreAllMocks();
});

const refused = (message: string, status = 409) =>
  HttpResponse.json({ error: { code: 'refused', message } }, { status });

describe('EventEditor, more', () => {
  it('says when there is nothing to copy, and copies one email in the singular', async () => {
    stubViewport('desktop');
    const writeText = vi.fn(() => Promise.resolve());
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await user.click(screen.getByRole('button', { name: 'Copy emails' }));
    expect(await screen.findByText('No emails to copy')).toBeInTheDocument();
    server.use(
      http.get('*/api/admin/club-events/1/emails', () =>
        HttpResponse.json({ emails: ['ike.hadley@example.com'] }),
      ),
    );
    await user.click(screen.getByRole('button', { name: 'Copy emails' }));
    expect(await screen.findByText('Copied 1 email')).toBeInTheDocument();
  });

  it('shows an alert when the emails cannot be fetched or copied', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/admin/club-events/1/emails', () =>
        refused('Could not read the emails.', 500),
      ),
    );
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Copy emails' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not read the emails.');
  });

  it('shows a plain alert when the clipboard throws a non-error', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/admin/club-events/1/emails', () =>
        HttpResponse.json({ emails: ['a@example.com'] }),
      ),
    );
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    const writeText = vi.fn(() => Promise.reject('denied'));
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await user.click(screen.getByRole('button', { name: 'Copy emails' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not copy the emails.');
  });

  it('shows an alert when the CSV is refused', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/admin/club-events/1/roster.csv', () =>
        refused('The CSV is not available.', 500),
      ),
    );
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Export CSV' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('The CSV is not available.');
  });

  it('restores a cancelled club event', async () => {
    stubViewport('desktop');
    let restored = false;
    server.use(
      http.post('*/api/admin/club-events/1/restore', () => {
        restored = true;
        return HttpResponse.json(adminEvent);
      }),
    );
    const { user } = renderWithProviders(
      <EventEditor event={{ ...adminEvent, state: 'cancelled' }} onDeleted={vi.fn()} />,
      { role: 'admin' },
    );
    expect(screen.queryByRole('button', { name: 'Cancel event' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Restore' }));
    expect(restored).toBe(false);
    const sheet = within(screen.getByRole('dialog'));
    expect(sheet.getByText('Restore this club event?')).toBeInTheDocument();
    await user.click(sheet.getByRole('button', { name: 'Restore' }));
    await waitFor(() => expect(restored).toBe(true));
    expect(await screen.findByText('Club event restored')).toBeInTheDocument();
  });

  it('shows Restore as a primary button', async () => {
    stubViewport('desktop');
    const { user } = renderWithProviders(
      <EventEditor event={{ ...adminEvent, state: 'cancelled' }} onDeleted={vi.fn()} />,
      { role: 'admin' },
    );
    await user.click(screen.getByRole('button', { name: 'Restore' }));
    expect(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Restore' }).className,
    ).toContain('bg-primary');
  });

  it('keeps Delete as a danger button, and its error does not come back after Keep it', async () => {
    stubViewport('desktop');
    server.use(http.delete('*/api/admin/club-events/1', () => refused('Could not delete.')));
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    const danger = within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' });
    expect(danger.className).not.toContain('bg-primary');
    await user.click(danger);
    expect(await within(screen.getByRole('dialog')).findByRole('alert')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Keep it' }));
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(within(screen.getByRole('dialog')).queryByRole('alert')).not.toBeInTheDocument();
  });

  it('links to the member page for the club event', () => {
    stubViewport('desktop');
    renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, { role: 'admin' });
    expect(screen.getByRole('link', { name: 'Open member page' })).toHaveAttribute(
      'href',
      '/club-events/1',
    );
  });

  it('shows why a cancel, a restore or a delete was refused', async () => {
    stubViewport('desktop');
    server.use(
      http.post('*/api/admin/club-events/1/cancel', () => refused('Already cancelled.')),
      http.post('*/api/admin/club-events/1/restore', () => refused('Already in the past.')),
      http.delete('*/api/admin/club-events/1', () => refused('Could not delete.')),
    );
    const first = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    await first.user.click(screen.getByRole('button', { name: 'Cancel event' }));
    await first.user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel event' }),
    );
    expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent(
      'Already cancelled.',
    );
    await first.user.click(screen.getByRole('button', { name: 'Keep it' }));
    await first.user.click(screen.getByRole('button', { name: 'Delete' }));
    await first.user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }),
    );
    expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent(
      'Could not delete.',
    );
    first.unmount();
    const second = renderWithProviders(
      <EventEditor event={{ ...adminEvent, state: 'cancelled' }} onDeleted={vi.fn()} />,
      { role: 'admin' },
    );
    await second.user.click(screen.getByRole('button', { name: 'Restore' }));
    await second.user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Restore' }),
    );
    expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent(
      'Already in the past.',
    );
  });

  it('says Saved after the form saves', async () => {
    stubViewport('desktop');
    server.use(http.patch('*/api/admin/club-events/1', () => HttpResponse.json(adminEvent)));
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Saved')).toBeInTheDocument();
  });

  it('keeps the club event when the delete is called off', async () => {
    stubViewport('desktop');
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Keep it' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('keeps one live region mounted and clears the older message when a new one arrives', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/admin/club-events/1/roster.csv', () =>
        refused('The CSV is not available.', 500),
      ),
      http.patch('*/api/admin/club-events/1', () => HttpResponse.json(adminEvent)),
    );
    const { user, container } = renderWithProviders(
      <EventEditor event={adminEvent} onDeleted={vi.fn()} />,
      { role: 'admin' },
    );
    const live = container.querySelector('[aria-live="polite"]');
    expect(live).not.toBeNull();
    await user.click(screen.getByRole('button', { name: 'Export CSV' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('The CSV is not available.');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Saved')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(container.querySelector('[aria-live="polite"]')).toBe(live);
    await user.click(screen.getByRole('button', { name: 'Export CSV' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText('Saved')).not.toBeInTheDocument();
  });

  it('says plainly when the clipboard is missing', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/admin/club-events/1/emails', () =>
        HttpResponse.json({ emails: ['a@example.com'] }),
      ),
    );
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });
    await user.click(screen.getByRole('button', { name: 'Copy emails' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not copy the emails.');
  });

  it('shows an alert, not a skeleton, when the sign-ups cannot be loaded', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/admin/club-events/1/roster', () => refused('No sign-ups for you.', 500)),
    );
    renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, { role: 'admin' });
    expect(await screen.findByRole('alert')).toHaveTextContent('No sign-ups for you.');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
