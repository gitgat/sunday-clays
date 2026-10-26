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

  it('says how many rounds marked * are not in the averages', async () => {
    renderWithProviders(
      <ProfileHero
        shooter={{ ...hadleyDetail, stats: { ...hadleyDetail.stats, n_excluded: 2 } }}
        isPlaceholderData={false}
      />,
    );
    expect(await screen.findByText('2 rounds marked * not in the average')).toBeInTheDocument();
  });

  it('shows a dash and the note when the only round in the window was thrown out', async () => {
    const window_stats = {
      ...hadleyDetail.stats,
      n_rounds: 1,
      n_events: 1,
      n_excluded: 1,
      avg_score: null,
      median_score: null,
      best_score: null,
      avg_adjusted: null,
    };
    renderWithProviders(
      <ProfileHero shooter={{ ...hadleyDetail, window_stats }} isPlaceholderData={false} />,
      { route: '/shooters/1?since=2026-10-25' },
    );
    expect(await screen.findByText('1 round marked * not in the average')).toBeInTheDocument();
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(1);
  });
});
