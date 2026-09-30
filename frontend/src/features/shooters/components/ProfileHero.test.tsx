import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { hadleyDetail } from '../mocks';
import { ProfileHero } from './ProfileHero';

describe('ProfileHero', () => {
  it('marks the windowed row busy while another window loads', async () => {
    renderWithProviders(<ProfileHero shooter={hadleyDetail} isPlaceholderData />);
    expect(await screen.findByLabelText('Loading this window')).toBeInTheDocument();
  });

  it('is not busy once the window has loaded', async () => {
    renderWithProviders(<ProfileHero shooter={hadleyDetail} isPlaceholderData={false} />);
    await screen.findByRole('heading', { name: /^In the last 8 weeks/ });
    expect(screen.queryByLabelText('Loading this window')).toBeNull();
  });
});
