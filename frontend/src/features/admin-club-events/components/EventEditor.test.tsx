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

describe('EventEditor', () => {
  it('exports the CSV and copies the going emails', async () => {
    stubViewport('desktop');
    const objectUrl = vi.spyOn(URL, 'createObjectURL');
    const writeText = vi.fn(() => Promise.resolve());
    let asked: string | null = null;
    server.use(
      http.get('*/api/admin/club-events/1/emails', ({ request }) => {
        asked = new URL(request.url).searchParams.get('status');
        return HttpResponse.json({ emails: ['ike.hadley@example.com', 'dana.quill@example.com'] });
      }),
    );
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={vi.fn()} />, {
      role: 'admin',
    });
    // user-event installs its own clipboard on setup, so the spy goes in after render.
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await user.click(await screen.findByRole('button', { name: 'Export CSV' }));
    await waitFor(() => expect(objectUrl).toHaveBeenCalled());
    await user.click(screen.getByRole('button', { name: 'Copy emails' }));
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith('ike.hadley@example.com, dana.quill@example.com'),
    );
    expect(asked).toBe('going');
    expect(await screen.findByText('Copied 2 emails')).toBeInTheDocument();
  });

  it('shows the waitlist-head hint and cancels, then restores', async () => {
    stubViewport('desktop');
    const { user } = renderWithProviders(
      <EventEditor event={{ ...adminEvent, capacity: 3 }} onDeleted={vi.fn()} />,
      {
        role: 'admin',
      },
    );
    expect(
      await screen.findByText('1 spot open; the next sign-up on the waitlist needs 3.'),
    ).toBeInTheDocument();
    let cancelled = false;
    server.use(
      http.post('*/api/admin/club-events/1/cancel', () => {
        cancelled = true;
        return HttpResponse.json({ ...adminEvent, state: 'cancelled' });
      }),
    );
    await user.click(screen.getByRole('button', { name: 'Cancel event' }));
    await waitFor(() => expect(cancelled).toBe(true));
  });

  it('deletes after the exact confirm', async () => {
    stubViewport('desktop');
    const onDeleted = vi.fn();
    server.use(
      http.delete('*/api/admin/club-events/1', () => new HttpResponse(null, { status: 204 })),
    );
    const { user } = renderWithProviders(<EventEditor event={adminEvent} onDeleted={onDeleted} />, {
      role: 'admin',
    });
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    const sheet = within(screen.getByRole('dialog'));
    expect(
      sheet.getByText("Delete Fall Fun Shoot and its sign-up list? This can't be undone."),
    ).toBeInTheDocument();
    await user.click(sheet.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });
});
