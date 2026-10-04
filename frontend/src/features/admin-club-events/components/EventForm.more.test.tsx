import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { adminEvent } from '../mocks';
import { EventForm } from './EventForm';

describe('EventForm, more', () => {
  it('keeps a hand-edited deadline when the date changes, and clearing the date leaves it alone', async () => {
    const { user } = renderWithProviders(<EventForm event={null} onSaved={vi.fn()} />, {
      role: 'admin',
    });
    await user.type(screen.getByLabelText('Date'), '2026-10-17');
    await user.clear(screen.getByLabelText('Date'));
    expect(screen.getByLabelText('Sign-up deadline date')).toHaveValue('2026-10-16');
    await user.clear(screen.getByLabelText('Sign-up deadline date'));
    await user.type(screen.getByLabelText('Sign-up deadline date'), '2026-10-10');
    await user.clear(screen.getByLabelText('Deadline time'));
    await user.type(screen.getByLabelText('Deadline time'), '18:30');
    await user.type(screen.getByLabelText('Date'), '2026-10-24');
    expect(screen.getByLabelText('Sign-up deadline date')).toHaveValue('2026-10-10');
    expect(screen.getByLabelText('Deadline time')).toHaveValue('18:30');
  });

  it('hides the guest limit when guests are off, and saves an edit', async () => {
    let body: unknown = null;
    server.use(
      http.patch('*/api/admin/club-events/1', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(adminEvent);
      }),
    );
    const onSaved = vi.fn();
    const { user } = renderWithProviders(<EventForm event={adminEvent} onSaved={onSaved} />, {
      role: 'admin',
    });
    expect(screen.getByLabelText('Most guests each')).toHaveValue(2);
    await user.click(screen.getByRole('switch', { name: 'Guests allowed' }));
    expect(screen.queryByLabelText('Most guests each')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(1));
    expect(body).toMatchObject({ allow_guests: false, max_guests: 0, capacity: 20 });
  });
});
