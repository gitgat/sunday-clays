import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { adminEvent } from '../mocks';
import { EventForm } from './EventForm';

describe('EventForm', () => {
  it('creates an event; the deadline follows the start until it is edited', async () => {
    let body: unknown = null;
    server.use(
      http.post('*/api/admin/club-events', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(adminEvent, { status: 201 });
      }),
    );
    const onSaved = vi.fn();
    const { user } = renderWithProviders(<EventForm event={null} onSaved={onSaved} />, {
      role: 'admin',
    });
    await user.type(screen.getByLabelText('Title'), 'Fall Fun Shoot');
    await user.type(screen.getByLabelText('Date'), '2026-10-17');
    await user.type(screen.getByLabelText('Start time'), '10:00');
    expect(screen.getByLabelText('Sign-up deadline date')).toHaveValue('2026-10-16');
    expect(screen.getByLabelText('Deadline time')).toHaveValue('20:00');
    await user.type(screen.getByLabelText('Notes'), 'Bring a chair.');
    expect(screen.getByText('14 / 2,000')).toBeInTheDocument();
    expect(screen.getByText('Leave empty for no limit')).toBeInTheDocument();
    await user.click(screen.getByRole('switch', { name: 'Guests allowed' }));
    await user.clear(screen.getByLabelText('Most guests each'));
    await user.type(screen.getByLabelText('Most guests each'), '2');
    await user.click(screen.getByRole('button', { name: 'Create event' }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(adminEvent.id));
    expect(body).toEqual({
      title: 'Fall Fun Shoot',
      starts_local: '2026-10-17T10:00',
      deadline_local: '2026-10-16T20:00',
      notes: 'Bring a chair.',
      capacity: null,
      allow_guests: true,
      max_guests: 2,
    });
  });

  it('shows the server message next to the button', async () => {
    server.use(
      http.post('*/api/admin/club-events', () =>
        HttpResponse.json(
          { error: { code: 'starts_in_past', message: 'Pick a start time in the future.' } },
          { status: 400 },
        ),
      ),
    );
    const { user } = renderWithProviders(<EventForm event={null} onSaved={vi.fn()} />, {
      role: 'admin',
    });
    await user.type(screen.getByLabelText('Title'), 'Banquet');
    await user.type(screen.getByLabelText('Date'), '2020-01-05');
    await user.type(screen.getByLabelText('Start time'), '18:00');
    await user.click(screen.getByRole('button', { name: 'Create event' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Pick a start time in the future.');
  });

  it('edits an event with its club-time values and says why a capacity was refused', async () => {
    server.use(
      http.patch('*/api/admin/club-events/:id', () =>
        HttpResponse.json(
          {
            error: {
              code: 'capacity_below_going',
              message: '4 spots are already taken. Remove people first, or set at least 4.',
            },
          },
          { status: 409 },
        ),
      ),
    );
    const { user } = renderWithProviders(<EventForm event={adminEvent} onSaved={vi.fn()} />, {
      role: 'admin',
    });
    expect(screen.getByLabelText('Date')).toHaveValue('2026-10-17');
    expect(screen.getByLabelText('Start time')).toHaveValue('23:30');
    expect(screen.getByLabelText('Sign-up deadline date')).toHaveValue('2026-10-16');
    await user.clear(screen.getByLabelText('Capacity'));
    await user.type(screen.getByLabelText('Capacity'), '3');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '4 spots are already taken. Remove people first, or set at least 4.',
    );
  });
});
