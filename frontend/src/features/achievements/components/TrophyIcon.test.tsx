import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../trophyArt.gen', () => ({
  trophyArt: {
    'clays_broken-gold': {
      src: '/trophies/clays_broken-gold.webp',
      src128: '/trophies/clays_broken-gold@128.webp',
    },
    doubleheader: { src: '/trophies/doubleheader.webp', src128: '/trophies/doubleheader@128.webp' },
  },
}));

import { TrophyIcon } from './TrophyIcon';

describe('TrophyIcon', () => {
  it('uses the 256 px art when the manifest has the metal variant', () => {
    const { container } = render(
      <TrophyIcon artKey="clays_broken" metal="gold" locked={false} size={256} />,
    );
    const img = container.querySelector('img');
    expect(img).toHaveAttribute('src', '/trophies/clays_broken-gold.webp');
    expect(img).toHaveAttribute('width', '256');
  });

  it('offers both art sizes through srcSet so 2x displays get the sharp one', () => {
    const { container } = render(
      <TrophyIcon artKey="clays_broken" metal="gold" locked={false} size={96} />,
    );
    const img = container.querySelector('img');
    expect(img).toHaveAttribute(
      'srcset',
      '/trophies/clays_broken-gold@128.webp 128w, /trophies/clays_broken-gold.webp 256w',
    );
    expect(img).toHaveAttribute('sizes', '96px');
  });

  it('uses the 128 px art at small sizes', () => {
    const { container } = render(
      <TrophyIcon artKey="clays_broken" metal="gold" locked={false} size={48} />,
    );
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      '/trophies/clays_broken-gold@128.webp',
    );
  });

  it('looks up one-off art without a metal suffix', () => {
    const { container } = render(
      <TrophyIcon artKey="doubleheader" metal={null} locked={false} size={64} />,
    );
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      '/trophies/doubleheader@128.webp',
    );
  });

  it('falls back to an SVG trophy tinted with the metal colour', () => {
    const { container } = render(
      <TrophyIcon artKey="events" metal="diamond" locked={false} size={64} />,
    );
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('svg circle')).toHaveAttribute('stroke', '#9FD8E6');
  });

  it('tints one-off fallbacks with the accent', () => {
    const { container } = render(
      <TrophyIcon artKey="rain" metal={null} locked={false} size={64} />,
    );
    expect(container.querySelector('svg circle')).toHaveAttribute('stroke', '#E8A77A');
  });

  it('greys out locked trophies whether art exists or not', () => {
    const art = render(<TrophyIcon artKey="doubleheader" metal={null} locked size={64} />);
    expect(art.container.querySelector('img')).toHaveStyle({
      opacity: '0.35',
      filter: 'grayscale(1)',
    });
    const fallback = render(<TrophyIcon artKey="rain" metal={null} locked size={64} />);
    const svg = fallback.container.querySelector('svg');
    expect(svg?.style.opacity).toBe('0.35');
    expect(svg?.style.filter).toBe('grayscale(1)');
  });
});
