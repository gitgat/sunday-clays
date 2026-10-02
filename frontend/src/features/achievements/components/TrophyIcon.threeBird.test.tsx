import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TrophyIcon } from './TrophyIcon';

// Unmocked: reads the real generated manifest, so it proves the built art is wired in.
describe('TrophyIcon with the generated manifest', () => {
  it('renders the 3-Bird Shoot art (the clays_thrown gold files) instead of the SVG fallback', () => {
    const { container } = render(
      <TrophyIcon artKey="three_bird_shoot" metal={null} locked={false} size={64} />,
    );
    const img = container.querySelector('img');
    expect(img).toHaveAttribute('src', '/trophies/clays_thrown-gold@128.webp');
    expect(container.querySelector('svg')).toBeNull();
  });
});
