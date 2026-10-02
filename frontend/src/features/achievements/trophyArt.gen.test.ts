import { describe, expect, it } from 'vitest';
import { trophyArt } from './trophyArt.gen';

const STEM = /^[a-z0-9_]+(-(bronze|silver|gold|platinum|diamond))?$/;

// A key that reuses another key's art points at that key's files (Plan 17 T10).
const REUSED: Record<string, string> = { three_bird_shoot: 'clays_thrown-gold' };

describe('trophyArt.gen', () => {
  it('maps each art stem to its 256 px and 128 px medallions', () => {
    const stems = Object.keys(trophyArt);
    expect(stems.filter((stem) => !STEM.test(stem))).toEqual([]);
    expect(Object.values(trophyArt)).toEqual(
      stems.map((stem) => ({
        src: `/trophies/${REUSED[stem] ?? stem}.webp`,
        src128: `/trophies/${REUSED[stem] ?? stem}@128.webp`,
      })),
    );
  });
});
