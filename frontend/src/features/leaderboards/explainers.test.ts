import { describe, expect, it } from 'vitest';

import { METRICS } from './labels';
import { boardExplainer, explainers, type BoardKind } from './explainers';

const KINDS: readonly BoardKind[] = ['season', 'ytd', 'rolling_12', 'all_time', 'custom'];

const sources = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

describe('leaderboard explainers', () => {
  it('has an entry for every ChartFrame urlKey in the feature', () => {
    const keys = Object.values(sources).flatMap((text) =>
      [...text.matchAll(/urlKey="([^"]+)"/g)].map((match) => match[1]),
    );
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) expect(explainers, key).toHaveProperty(String(key));
  });

  it('explains every measure for every kind of board, tagged with the time window it follows', () => {
    for (const metric of METRICS) {
      for (const kind of KINDS) {
        const entry = boardExplainer(metric.value, kind);
        const text = JSON.stringify(entry);
        expect(entry.scope, `${metric.value} ${kind}`).toBe('windowed');
        expect(entry.computed.length, metric.value).toBeGreaterThan(2);
        expect(text, metric.value).not.toMatch(
          /\bclass|\bhe\b|\bshe\b|\bhis\b|\bher\b|\bevents?\b/i,
        );
      }
    }
  });

  it('says fullscreen and the CSV list everyone, not only the top ten', () => {
    const entry = boardExplainer('avg_score', 'season');
    expect(entry.read).toContain(
      'Ties share a place, and a tie for tenth can be cut from the chart. Fullscreen, the table below and the CSV download list everyone.',
    );
    expect(entry.computed[0]).toBe(
      'The first ten rows of the standings (every row in fullscreen and the CSV); bar length is that measure’s value for each shooter.',
    );
  });

  it('states the exact rules the backend applies', () => {
    const points = JSON.stringify(boardExplainer('season_points', 'season'));
    expect(points).toContain('10, 8, 6, 5, 4, 3, 2 and 1');
    expect(points).toContain('a win is worth 11');
    const gain = JSON.stringify(boardExplainer('rating_gain', 'all_time'));
    expect(gain).toContain('10th round');
    expect(gain).toContain('15 or more');
    expect(gain).toContain('Only shooters whose rating went up are listed');
    expect(JSON.stringify(boardExplainer('rating_gain', 'season'))).toContain(
      'last 8 weeks: 3 or more inside',
    );
  });

  it('describes each period, and says the time window picks the dates', () => {
    const season = boardExplainer('wins', 'season').computed.join(' ');
    expect(season).toContain('the last 8 Sundays, which is the 56 days ending on the board’s date');
    expect(season).toContain('never restarts in January');
    expect(season).toContain('The time window at the top picks the dates');
    const ytd = boardExplainer('wins', 'ytd').computed.join(' ');
    expect(ytd).toContain('January 1 of that year up to the board’s date');
    expect(boardExplainer('wins', 'rolling_12').computed.join(' ')).toContain('the 364 days');
    expect(boardExplainer('wins', 'all_time').computed.join(' ')).toContain('every round');
  });

  it('gives each average period its own qualifying rule, matching the backend', () => {
    const rule = (kind: BoardKind) => boardExplainer('avg_score', kind).computed.join(' ');
    expect(rule('season')).toContain('40% of the Sundays with scores in the period');
    expect(rule('ytd')).toContain('never more than 5');
    expect(rule('rolling_12')).toContain('8 or more rounds');
    expect(rule('all_time')).toContain('15 or more rounds');
    expect(boardExplainer('wins', 'season').computed.join(' ')).not.toContain('To be listed');
  });

  it('describes a board from a start date (3M, 6M, Custom) and its thresholds', () => {
    const avg = boardExplainer('avg_score', 'custom').computed.join(' ');
    expect(avg).toContain('from the start of your time window');
    expect(avg).toContain('40% of the Sundays with scores in your dates (at most 5)');
    expect(avg).toContain('never more than 15');
    expect(boardExplainer('avg_adjusted', 'custom').computed.join(' ')).toContain(
      '40% of the Sundays',
    );
    expect(boardExplainer('rating_gain', 'custom').computed.join(' ')).toContain(
      'Needs 10 or more rounds before the start date and 5 or more inside your dates.',
    );
    expect(boardExplainer('season_points', 'custom').computed.join(' ')).toContain(
      'Points are added up over the Sundays in your dates; places are always against the whole field that day.',
    );
    expect(boardExplainer('wins', 'custom').computed.join(' ')).toContain('scores in your dates');
  });
});
