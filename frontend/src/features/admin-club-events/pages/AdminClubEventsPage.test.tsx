import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../../test/msw/server';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { AdminClubEventsPage } from './AdminClubEventsPage';

describe('AdminClubEventsPage', () => {
  it('switches between the Events and Contacts tabs', async () => {
    stubViewport('desktop');
    const { user } = renderWithProviders(<AdminClubEventsPage />, { role: 'admin' });
    expect(await screen.findByRole('button', { name: 'New event' })).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Contacts' }));
    expect(await screen.findByRole('button', { name: 'Add email' })).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Events' }));
    expect(await screen.findByRole('button', { name: 'New event' })).toBeInTheDocument();
  });

  it('tells the organizer members cannot see club events until the switch is on', async () => {
    stubViewport('desktop');
    renderWithProviders(<AdminClubEventsPage />, { role: 'admin' });
    const link = await screen.findByRole('link', { name: 'Features' });
    expect(link.parentElement).toHaveTextContent(
      "Members can't see club events until Club events is turned on in Features.",
    );
    expect(screen.getByRole('link', { name: 'Features' })).toHaveAttribute(
      'href',
      '/admin/features',
    );
  });

  it('shows no notice once the switch is on', async () => {
    stubViewport('desktop');
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: { events: true } })));
    renderWithProviders(<AdminClubEventsPage />, { role: 'admin' });
    expect(await screen.findByRole('button', { name: 'New event' })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText(/Members can't see club events/)).not.toBeInTheDocument();
  });
});
