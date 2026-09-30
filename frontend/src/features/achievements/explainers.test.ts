import { describe, expect, it } from 'vitest';
import { explainers } from './explainers';

const sources = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

describe('achievement explainers', () => {
  it('has an entry for every ChartFrame urlKey in the feature', () => {
    const keys = Object.values(sources).flatMap((text) =>
      [...text.matchAll(/urlKey="([^"]+)"/g)].map((match) => match[1]),
    );
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) expect(explainers, key).toHaveProperty(String(key));
  });

  it('describes trophy progress accurately', () => {
    const text = JSON.stringify(explainers['trophy-progress']);
    expect(text).not.toContain('one shot away');
    expect(text).not.toContain('every round you have shot');
    expect(text).toContain('Each family counts its own thing');
  });

  it('gives every entry a what and a computed part', () => {
    for (const [key, entry] of Object.entries(explainers)) {
      expect(entry.what.length, key).toBeGreaterThan(10);
      expect(entry.computed.length, key).toBeGreaterThan(0);
    }
  });
});
