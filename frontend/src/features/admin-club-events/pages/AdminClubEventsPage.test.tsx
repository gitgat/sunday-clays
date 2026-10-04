import { screen } from '@testing-library/react';
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
});
