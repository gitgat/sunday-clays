import { describe, expect, it } from 'vitest';

import { explainers, raceExplainer, raceIntro } from './explainers';
import type { RaceMode } from './labels';

const sources = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

const NEUTRAL = /\bclass|\bhe\b|\bshe\b|\bhis\b|\bher\b|\bevents?\b/i;
const MODES: RaceMode[] = ['rolling_12', 'season', 'ytd'];

describe('race explainers', () => {
  it('has an entry for every ChartFrame urlKey in the feature', () => {
    const keys = Object.values(sources).flatMap((text) =>
      [...text.matchAll(/urlKey="([^"]+)"/g)].map((match) => match[1]),
    );
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) expect(explainers, key).toHaveProperty(String(key));
  });

  it('is plain and neutral, and the base copy no longer mentions a Year control', () => {
    for (const [key, entry] of Object.entries(explainers)) {
      expect(JSON.stringify(entry), key).not.toMatch(NEUTRAL);
      expect(JSON.stringify(entry), key).not.toContain('Year control');
    }
    for (const mode of MODES) {
      for (const key of ['race-bars', 'race-bump'] as const) {
        const entry = raceExplainer(key, mode);
        expect(entry.scope).toBe('windowed');
        expect(JSON.stringify(entry)).not.toMatch(NEUTRAL);
        expect(entry.computed.at(-1)).toContain('The time window at the top picks the Sundays');
      }
    }
  });

  it('says how much fullscreen and the CSV download add', () => {
    for (const mode of MODES) {
      expect(raceExplainer('race-bars', mode).read).toContain(
        'Fullscreen draws the top 50; its table and the CSV download list the same top 50 ranked that Sunday.',
      );
      const bump = raceExplainer('race-bump', mode).read ?? [];
      expect(bump).toContain(
        'Fullscreen follows the top 50; its table and the CSV download have the top 50 on every Sunday.',
      );
      expect(bump.join(' ')).toContain('outside the top ten (top 50 in fullscreen) that Sunday.');
    }
  });

  it('states how each mode picks the Sundays and counts each step (checked against the backend)', () => {
    expect(raceExplainer('race-bars', 'rolling_12').computed.at(-1)).toContain(
      'the 364 days ending on that Sunday (the last 52 Sundays)',
    );
    expect(raceExplainer('race-bars', 'season').computed.at(-1)).toContain(
      'last 8 Sundays (56 days)',
    );
    expect(raceExplainer('race-bump', 'ytd').computed.at(-1)).toContain(
      'from 1 January up to that Sunday',
    );
  });
});

describe('race intro', () => {
  it('spells out the points and what each mode resets', () => {
    const rolling = raceIntro('rolling_12');
    expect(rolling.points).toContain(
      '1st place earns 10, 2nd 8, 3rd 6, 4th 5, 5th 4, 6th 3, 7th 2 and 8th 1, plus 1 for turning up',
    );
    expect(rolling.mode).toBe(
      'Last 12 months counts points from the last 52 Sundays. Each Sunday’s points drop off a year later, so there is no reset.',
    );
    expect(raceIntro('season').mode).toContain('no reset');
    expect(raceIntro('ytd').mode).toContain('resets every 1 January');
    expect(raceIntro('season').what).toContain('The time window at the top picks the Sundays');
  });
});
