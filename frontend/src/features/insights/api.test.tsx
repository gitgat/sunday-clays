import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { useHomeFeed, useShooterFeed, useSundayFeed } from './api';

function Probe() {
  const shooter = useShooterFeed(3);
  const sunday = useSundayFeed('2026-09-27');
  const home = useHomeFeed();
  return (
    <p>
      {String(shooter.data?.top.length ?? '-')}/{String(sunday.data?.as_of ?? '-')}/
      {String(home.data?.data_version ?? '-')}
    </p>
  );
}

describe('insight feed hooks', () => {
  it('load the shooter, Sunday and home feeds', async () => {
    renderWithProviders(<Probe />);
    expect(await screen.findByText('1/2026-09-27/7')).toBeInTheDocument();
  });
});
