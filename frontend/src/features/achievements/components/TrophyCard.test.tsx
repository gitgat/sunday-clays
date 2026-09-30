import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '../../../api/schema';
import { shareElementAsImage } from '../../../lib/share';
import { renderWithProviders } from '../../../test/render';
import { TrophyCard } from './TrophyCard';

vi.mock('../../../lib/share', () => ({ shareElementAsImage: vi.fn() }));

beforeEach(() => {
  vi.mocked(shareElementAsImage).mockReset();
});

const TROPHY: components['schemas']['TrophyOut'] = {
  code: 'clays_broken:3',
  family: 'clays_broken',
  name: 'Clays Broken',
  description: 'Lifetime clays broken',
  category: 'milestone',
  art_key: 'clays_broken',
  metal: 'silver',
  level: 3,
  threshold: 1000,
  label: '1,000 clays broken',
  repeatable: false,
  holders: 65,
  rarity_pct: 19.6,
  last_awarded: '2026-09-27',
};

describe('TrophyCard sharing', () => {
  it('keeps the trophy link and shares the card under the trophy code', async () => {
    vi.mocked(shareElementAsImage).mockResolvedValue('downloaded');
    const { user } = renderWithProviders(<TrophyCard trophy={TROPHY} />);
    expect(screen.getByRole('link', { name: /Clays Broken/ })).toHaveAttribute(
      'href',
      '/achievements/clays_broken%3A3',
    );
    await user.click(
      screen.getByRole('button', { name: 'Share image: Clays Broken, 1,000 clays broken' }),
    );
    const [element, filename] = vi.mocked(shareElementAsImage).mock.calls[0] ?? [];
    expect(element).toHaveTextContent('65 holders');
    expect(filename).toBe('sunday-clays-trophy-clays-broken-3.png');
  });

  it('names one-off trophies by their name alone', () => {
    renderWithProviders(
      <TrophyCard
        trophy={{
          ...TROPHY,
          code: 'first_win',
          name: 'First Win',
          label: null,
          metal: null,
          level: null,
          threshold: null,
        }}
      />,
    );
    expect(screen.getByRole('button', { name: 'Share image: First Win' })).toBeInTheDocument();
  });

  it('offers no share button for a trophy nobody has earned yet', () => {
    renderWithProviders(<TrophyCard trophy={{ ...TROPHY, holders: 0 }} />);
    expect(screen.getByRole('link', { name: /Clays Broken/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Share image/ })).not.toBeInTheDocument();
  });

  it('shows an icon-only share button beside the card, still 44 px and named', () => {
    renderWithProviders(<TrophyCard trophy={TROPHY} />);
    const button = screen.getByRole('button', { name: /^Share image/ });
    expect(button).not.toHaveTextContent('Share image');
    expect(button).toHaveClass('min-h-11', 'min-w-11');
  });
});
