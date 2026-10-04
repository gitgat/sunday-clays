import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { adminEvent } from '../mocks';
import { EventsTab } from './EventsTab';

describe('EventsTab', () => {
  it('lists events with their counts and opens one in the editor', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/admin/club-events', () =>
        HttpResponse.json([
          adminEvent,
          { ...adminEvent, id: 2, title: 'Banquet', state: 'cancelled' },
        ]),
      ),
    );
    const { user } = renderWithProviders(<EventsTab />, { role: 'admin' });
    const list = await screen.findByRole('list', { name: 'Club events' });
    expect(within(list).getByText('2026-10-17 · 1 going · 1 on the waitlist')).toBeInTheDocument();
    expect(
      within(list).getByText('2026-10-17 · 1 going · 1 on the waitlist · Cancelled'),
    ).toBeInTheDocument();
    await user.click(within(list).getByRole('button', { name: /Fall Fun Shoot/ }));
    expect(await screen.findByRole('button', { name: 'Save changes' })).toBeInTheDocument();
    await user.click(within(list).getByRole('button', { name: /Banquet/ }));
    expect(await screen.findByRole('button', { name: 'Restore' })).toBeInTheDocument();
  });

  it('says so when there are no club events, and opens the create form', async () => {
    stubViewport('desktop');
    server.use(http.get('*/api/admin/club-events', () => HttpResponse.json([])));
    const { user } = renderWithProviders(<EventsTab />, { role: 'admin' });
    expect(await screen.findByText('No club events yet.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'New event' }));
    expect(screen.getByRole('button', { name: 'Create event' })).toBeInTheDocument();
  });

  it('opens the new event in the editor after it is created', async () => {
    stubViewport('desktop');
    server.use(
      http.post('*/api/admin/club-events', () => HttpResponse.json(adminEvent, { status: 201 })),
    );
    const { user } = renderWithProviders(<EventsTab />, { role: 'admin' });
    await user.click(await screen.findByRole('button', { name: 'New event' }));
    await user.type(screen.getByLabelText('Title'), 'Fall Fun Shoot');
    await user.type(screen.getByLabelText('Date'), '2026-10-17');
    await user.type(screen.getByLabelText('Start time'), '10:00');
    await user.click(screen.getByRole('button', { name: 'Create event' }));
    expect(await screen.findByRole('button', { name: 'Save changes' })).toBeInTheDocument();
  });

  it('closes the editor after a delete', async () => {
    stubViewport('desktop');
    server.use(
      http.delete('*/api/admin/club-events/1', () => new HttpResponse(null, { status: 204 })),
    );
    const { user } = renderWithProviders(<EventsTab />, { role: 'admin' });
    await user.click(await screen.findByRole('button', { name: /Fall Fun Shoot/ }));
    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument(),
    );
  });
});
