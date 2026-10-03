import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { explainers } from './explainers';

const sources = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});
const allText = Object.values(sources).join('\n');

describe('club explainers', () => {
  it('has an entry for every ChartFrame and ChartCard urlKey in the feature', () => {
    const keys = [...allText.matchAll(/urlKey="([^"]+)"/g)].map((match) => match[1]);
    expect(keys.length).toBeGreaterThanOrEqual(12);
    for (const key of keys) expect(explainers, key).toHaveProperty(String(key));
  });

  it('has an entry for every stat and list the feature explains', () => {
    const ids = [...allText.matchAll(/explainers\['([^']+)'\]/g)].map((match) => match[1]);
    expect(ids.length).toBeGreaterThanOrEqual(7);
    for (const id of ids) expect(explainers, id).toHaveProperty(String(id));
  });

  it('gives every entry a what and a computed part, and a scope for each chart', () => {
    for (const [key, entry] of Object.entries(explainers)) {
      expect(entry.what.length, key).toBeGreaterThan(10);
      expect(entry.computed.length, key).toBeGreaterThan(0);
    }
  });

  it('follows the time window only where the chart is a time series or takes dates', () => {
    const windowed = Object.entries(explainers)
      .filter(([, entry]) => entry.scope === 'windowed')
      .map(([key]) => key);
    expect(windowed.sort()).toEqual([
      'att',
      'ctot',
      'diff',
      'first-rounds',
      'scores',
      'stat-clays',
      'stat-first',
      'stat-rounds',
      'stat-shooters',
      'stat-sundays',
      'turnout',
    ]);
  });

  it('says fullscreen and the CSV cover every Sunday', () => {
    const sentence =
      'The chart opens on the time window. Fullscreen shows every Sunday, and the CSV download has them all.';
    for (const key of ['att', 'scores', 'diff']) {
      expect(explainers[key]?.computed.join(' '), key).toContain(sentence);
    }
    expect(explainers.turnout?.computed.join(' ')).toContain(
      'On the page: only Sundays inside the time window. Fullscreen and the CSV download use every Sunday on record.',
    );
  });

  it('uses plain words: Sunday not event, no class wording, no he/she', () => {
    const text = JSON.stringify(Object.values(explainers));
    expect(text).not.toMatch(/\bevents?\b/i);
    expect(text).not.toMatch(/\bclass(es)?\b/i);
    expect(text).not.toMatch(/\b(he|she|his|her|hers)\b/i);
    expect(text).not.toMatch(/residual|percentile|parity/i);
  });

  it('describes guest conversion as a per-year group of guests', () => {
    const text = JSON.stringify(explainers.conv);
    expect(text).toContain('Of the guests first seen each year');
    expect(text).not.toContain('can top 100');
  });
});

describe('club milestone explainers (Plan 19)', () => {
  it('have the three new entries with their scopes and glossary terms', () => {
    expect(explainers['club-milestone']?.scope).toBe('all-time');
    expect(explainers['club-milestones']?.scope).toBe('all-time');
    expect(explainers.ctot?.scope).toBe('windowed');
    expect(explainers['club-milestone']?.terms).toEqual([
      'held-sunday',
      'special-shoot',
      'clays-thrown',
    ]);
    expect(explainers.ctot?.terms).toEqual(['clays-thrown', 'special-shoot', 'held-sunday']);
  });

  it('use no banned word', () => {
    const entries = ['club-milestone', 'club-milestones', 'ctot'].map((key) => explainers[key]);
    for (const text of allStrings(entries)) expect(text).not.toMatch(BANNED_WORDS);
  });
});
