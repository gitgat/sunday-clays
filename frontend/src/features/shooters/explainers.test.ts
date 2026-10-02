import { describe, expect, it } from 'vitest';
import { explainers } from './explainers';

const sources = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

describe('shooter explainers', () => {
  it('has an entry for every ChartFrame urlKey in the feature', () => {
    const keys = Object.values(sources).flatMap((text) =>
      [...text.matchAll(/urlKey="([^"]+)"/g)].map((match) => match[1]),
    );
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) expect(explainers, key).toHaveProperty(String(key));
  });

  it('gives every entry a what and a computed part, in neutral plain words', () => {
    for (const [key, entry] of Object.entries(explainers)) {
      const text = JSON.stringify(entry);
      expect(entry.what.length, key).toBeGreaterThan(10);
      expect(entry.computed.length, key).toBeGreaterThan(0);
      expect(text, key).not.toMatch(/\b(he|she|his|her|class|classes|event|events)\b/i);
      expect(text, key).not.toMatch(/percentile|residual|95% band|P10/i);
    }
  });

  it('marks the charts that follow the time window and the ones that ignore it', () => {
    expect(explainers.rating.scope).toBe('windowed');
    expect(explainers.trend.scope).toBe('windowed');
    // The distribution and the splits follow the window too (the server takes since / as_of).
    for (const key of ['dist', 'splits'] as const) {
      expect(explainers[key].scope, key).toBe('windowed');
    }
    for (const key of ['learn', 'cal'] as const) {
      expect(explainers[key].scope, key).toBe('all-time');
    }
    for (const key of ['win-rounds', 'win-average', 'win-best'] as const) {
      expect(explainers[key].scope, key).toBe('windowed');
    }
  });

  it('says fullscreen and the CSV download cover everything', () => {
    const text = (key: keyof typeof explainers) => JSON.stringify(explainers[key].computed);
    expect(text('rating')).toContain(
      'Opens on the time window. Fullscreen opens on all your history, and the CSV download has every point.',
    );
    expect(text('trend')).toContain(
      'Opens on the time window. Fullscreen shows every round you have shot, and the CSV download has them all.',
    );
    expect(text('finishes')).toContain(
      'Opens on the time window. Fullscreen shows every Sunday you finished, and the CSV download has them all.',
    );
    expect(text('cal')).toContain(
      'The fullscreen table and the CSV download cover every year you shot.',
    );
  });

  it('says the round-type filter covers special shoots, which no longer always show', () => {
    const text = explainers.cal.computed.join(' ');
    expect(text).not.toMatch(/special shoots always show/i);
    expect(text).toContain('special shoots included');
  });
});
