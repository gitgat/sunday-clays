import { describe, expect, it } from 'vitest';
import { METRICS } from '../../components/charts/explore';
import { CHOICES_EXPLAINER, METRIC_COPY, explainers, explorerExplainer } from './explainers';

const sources = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

describe('explorer explainers', () => {
  it('has an entry for every ChartFrame urlKey in the feature', () => {
    const keys = Object.values(sources).flatMap((text) =>
      [...text.matchAll(/urlKey="([^"]+)"/g)].map((match) => match[1]),
    );
    expect(keys).toContain('v');
    for (const key of keys) expect(explainers, key).toHaveProperty(String(key));
  });

  it('describes every metric', () => {
    expect(Object.keys(METRIC_COPY).sort()).toEqual([...METRICS].sort());
    for (const metric of METRICS) {
      const entry = explorerExplainer(metric, 'windowed');
      expect(entry.what.length, metric).toBeGreaterThan(10);
      expect(entry.computed.length, metric).toBeGreaterThan(1);
    }
  });

  it('says which dates the numbers cover', () => {
    expect(explorerExplainer('score', 'windowed').scope).toBe('windowed');
    expect(explorerExplainer('score', 'windowed').computed.join(' ')).toContain('time window');
    expect(explorerExplainer('score', 'all-time').scope).toBe('all-time');
    const own = explorerExplainer('score', undefined);
    expect(own).not.toHaveProperty('scope');
    expect(own.computed.join(' ')).toContain('Every Sunday on record.');
  });

  it('says fullscreen and the CSV download cover every Sunday, not just the window', () => {
    const windowed = explorerExplainer('score', 'windowed').computed.join(' ');
    expect(windowed).toContain(
      'On the page: only Sundays inside the time window at the top of the page (change it there). Fullscreen and the CSV download cover every Sunday.',
    );
    expect(explorerExplainer('score', undefined).computed.join(' ')).toContain(
      'Fullscreen and the CSV download can hold up to 5,000 rows.',
    );
  });

  it('uses plain words: no class wording, no jargon, no he/she', () => {
    const text = JSON.stringify([
      Object.values(METRIC_COPY),
      CHOICES_EXPLAINER,
      Object.values(explainers),
    ]);
    expect(text).not.toMatch(/\bclass(es)?\b/i);
    expect(text).not.toMatch(/\b(he|she|his|her|hers)\b/i);
    expect(text).not.toMatch(/residual/i);
  });
});
