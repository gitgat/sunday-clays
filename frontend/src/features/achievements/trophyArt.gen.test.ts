import { describe, expect, it } from 'vitest';
import { trophyArt } from './trophyArt.gen';

const STEM = /^[a-z0-9_]+(-(bronze|silver|gold|platinum|diamond))?$/;

describe('trophyArt.gen', () => {
  it('maps each art stem to its 256 px and 128 px medallions', () => {
    const stems = Object.keys(trophyArt);
    expect(stems.filter((stem) => !STEM.test(stem))).toEqual([]);
    expect(Object.values(trophyArt)).toEqual(
      stems.map((stem) => ({
        src: `/trophies/${stem}.webp`,
        src128: `/trophies/${stem}@128.webp`,
      })),
    );
  });
});
