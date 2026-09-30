import { describe, expect, it } from 'vitest';
import { artManifestKey, LOCKED_STYLE, METAL_COLORS } from './metals';

describe('metals', () => {
  it('builds manifest keys with a metal suffix only for tiers', () => {
    expect(artManifestKey('clays_broken', 'gold')).toBe('clays_broken-gold');
    expect(artManifestKey('doubleheader', null)).toBe('doubleheader');
  });

  it('uses the C12 metal colours and the locked style', () => {
    expect(METAL_COLORS).toEqual({
      bronze: '#C98B5B',
      silver: '#C9D1D6',
      gold: '#E3B34A',
      platinum: '#E6EEF2',
      diamond: '#9FD8E6',
    });
    expect(LOCKED_STYLE).toEqual({ opacity: 0.35, filter: 'grayscale(1)' });
  });
});
