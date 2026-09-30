import { describe, expect, it } from 'vitest';

import { explainers, recordsExplainer } from './explainers';

const sources = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

const NEUTRAL = /\bclass|\bhe\b|\bshe\b|\bhis\b|\bher\b|\bevents?\b/i;

describe('records explainers', () => {
  it('has an entry for every ChartFrame urlKey the feature passes', () => {
    // ShooterRecordChart takes its urlKey as a prop, so read the call sites too.
    const keys = Object.values(sources).flatMap((text) =>
      [...text.matchAll(/urlKey="([^"]+)"/g)].map((match) => match[1]),
    );
    expect(keys).toEqual(expect.arrayContaining(['rec-events', 'rec-streaks']));
    for (const key of keys) expect(explainers, key).toHaveProperty(String(key));
  });

  it('follows the time window, and is plain and neutral', () => {
    for (const [key, entry] of Object.entries(explainers)) {
      expect(entry.scope, key).toBe('windowed');
      expect(entry.computed.length, key).toBeGreaterThan(0);
      expect(JSON.stringify(entry), key).not.toMatch(NEUTRAL);
    }
  });

  it('says fullscreen and the CSV download list everyone', () => {
    expect(explainers['rec-events']?.what).toBe(
      'Who has come to the most Sundays: the top ten here, everyone in fullscreen and the CSV download.',
    );
    expect(explainers['rec-streaks']?.read).toContain(
      'Fullscreen and the CSV download list everyone with a streak.',
    );
    expect(
      recordsExplainer('rec-streaks', { since: '2024-01-07', asOf: '2024-12-29' }).read,
    ).toContain('Fullscreen and the CSV download list everyone with a streak.');
  });

  it('names the dates the time window picked', () => {
    const entry = recordsExplainer('rec-events', { since: '2024-01-07', asOf: '2024-12-29' });
    expect(entry.scope).toBe('windowed');
    expect(entry.computed).toContain(
      'Only Sundays from Jan 7, 2024 to Dec 29, 2024 count. The time window at the top picks them.',
    );
    expect(entry.computed.length).toBe((explainers['rec-events']?.computed.length ?? 0) + 1);
  });

  it('starts an unbounded window at the first Sunday', () => {
    expect(recordsExplainer('rec-events', { asOf: '2024-12-29' }).computed).toContain(
      'Only Sundays from the first Sunday to Dec 29, 2024 count. The time window at the top picks them.',
    );
  });

  it('tells streaks that a run from before the start counts from the start date', () => {
    const streaks = recordsExplainer('rec-streaks', { since: '2024-01-07', asOf: '2024-12-29' });
    expect(streaks.computed).toContain(
      'A run that began before the start date counts from the start date.',
    );
    expect((streaks.read ?? []).join(' ')).not.toContain('best run ever');
    expect(
      recordsExplainer('rec-events', { since: '2024-01-07', asOf: '2024-12-29' }).computed.join(
        ' ',
      ),
    ).not.toContain('start date counts');
    expect(JSON.stringify(streaks)).not.toMatch(NEUTRAL);
  });
});
