import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { useShooterFeed, useSundayFeed } from './api';

function Probe() {
  const shooter = useShooterFeed(3);
  const sunday = useSundayFeed('2026-09-27');
  return (
    <p>
      {String(shooter.data?.top.length ?? '-')}/{String(sunday.data?.as_of ?? '-')}
    </p>
  );
}

describe('insight feed hooks', () => {
  it('load the shooter and Sunday feeds', async () => {
    renderWithProviders(<Probe />);
    expect(await screen.findByText('1/2026-09-27')).toBeInTheDocument();
  });
});
