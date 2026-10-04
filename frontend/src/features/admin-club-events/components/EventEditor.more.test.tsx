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
    await waitFor(() => expect(restored).toBe(true));
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
    expect(await screen.findByRole('alert')).toHaveTextContent('Already cancelled.');
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
    expect(await screen.findByRole('alert')).toHaveTextContent('Already in the past.');
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
});
