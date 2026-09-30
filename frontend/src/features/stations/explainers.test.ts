import { describe, expect, it } from 'vitest';
import { explainers } from './explainers';

const sources = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

describe('station explainers', () => {
  it('has an entry for every ChartFrame urlKey in the feature', () => {
    const keys = Object.values(sources).flatMap((text) =>
      [...text.matchAll(/urlKey="([^"]+)"/g)].map((match) => match[1]),
    );
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) expect(explainers, key).toHaveProperty(String(key));
  });

  it('gives every entry a what and a computed part, in neutral words', () => {
    for (const [key, entry] of Object.entries(explainers)) {
      expect(entry.what.length, key).toBeGreaterThan(10);
      expect(entry.computed.length, key).toBeGreaterThan(0);
      const text = JSON.stringify(entry);
      expect(text, key).not.toMatch(
        /\b(he|she|his|her|him|hers|himself|herself|class|event|events|95%|CI)\b/i,
      );
    }
  });

  it('says every entry uses only Sundays that have a station sheet', () => {
    for (const [key, entry] of Object.entries(explainers)) {
      expect(entry.computed.join(' '), key).toMatch(/only Sundays with a station sheet/i);
    }
  });

  it('says fullscreen and the CSV download go beyond the card', () => {
    expect(explainers.sttime?.computed.join(' ')).toContain(
      'The chart and its table cover the time window you picked. Fullscreen shows every Sunday, and the CSV download has them all.',
    );
    expect(explainers.sttime?.computed.join(' ')).not.toContain('drag the axis');
    expect(explainers.stdelta?.computed).toContain(
      'The CSV download lists every station; a station shot fewer than twice has no versus-field number.',
    );
  });

  it('says a lettered station is counted apart from its number', () => {
    for (const key of ['station-summary', 'sthit']) {
      expect(explainers[key]?.computed.join(' '), key).toContain(
        'A lettered station such as 7A is its own station',
      );
    }
  });

  it('tags only the trend chart (the page’s scope line names the rest), never "All time"', () => {
    expect(explainers.sttime?.scope).toBe('windowed');
    for (const [key, entry] of Object.entries(explainers)) {
      if (key !== 'sttime') expect(entry.scope, key).toBeUndefined();
    }
  });

  it('says the time window decides which Sundays count', () => {
    for (const [key, entry] of Object.entries(explainers)) {
      expect(entry.computed.join(' '), key).toMatch(/inside the time window you picked/i);
    }
  });
});
