import { describe, expect, it } from 'vitest';
import page from './pages/WeatherPage.tsx?raw';
import { explainers } from './explainers';

const urlKeys = [...page.matchAll(/urlKey="([^"]+)"/g)].map((m) => m[1] as string);

describe('weather explainers', () => {
  it('finds the page ChartFrames', () => {
    expect(urlKeys.length).toBeGreaterThan(0);
  });

  it.each(urlKeys)('has copy for the %s chart', (key) => {
    const entry = explainers[key];
    expect(entry).toBeDefined();
    expect(entry?.what.length).toBeGreaterThan(0);
    expect(entry?.computed.length).toBeGreaterThan(0);
  });

  it('has copy for the stat blocks', () => {
    expect(explainers['conditions']).toBeDefined();
    expect(explainers['profile-sensitivity']).toBeDefined();
  });

  it.each(['wf', 'wr', 'conditions'])('says the round-type filter applies to %s', (key) => {
    expect(explainers[key]?.computed).toContain('The round-type filter applies.');
  });

  it.each(['wf', 'wr', 'wb', 'wt', 'conditions'])('tags %s with the time window', (key) => {
    expect(explainers[key]?.scope).toBe('windowed');
  });

  it.each(['ws', 'profile-sensitivity'])('tags %s as all-time and says so', (key) => {
    expect(explainers[key]?.scope).toBe('all-time');
    expect(explainers[key]?.computed.join(' ')).toContain('all history');
  });

  it('says estimates go to zero when the data cannot tell shooters apart', () => {
    const text = explainers['ws']?.computed.join(' ') ?? '';
    expect(text).toContain(
      'When the rounds cannot tell shooters apart on a measure, every estimate becomes zero',
    );
    expect(text).toContain('no one shows a weather effect at all');
  });

  it('says the club model line covers all history although the dots follow the window', () => {
    expect(explainers['wf']?.computed.join(' ')).toMatch(/all the way back, not just the window/);
  });

  it('never calls a shooter better or worse in some weather', () => {
    const text = JSON.stringify([
      explainers['ws'],
      explainers['profile-sensitivity'],
    ]).toLowerCase();
    for (const word of [
      'worse',
      'worst',
      'bad',
      'poor',
      'weak',
      'struggle',
      'his',
      'her',
      'she',
      'he ',
    ]) {
      expect(text).not.toMatch(new RegExp(`\\b${word.trim()}\\b`));
    }
  });

  it('says the band charts can be grouped by time of year, not only weather', () => {
    for (const key of ['wb', 'wt']) {
      expect(explainers[key]?.what).toContain('or time of year');
    }
  });

  it('avoids the words the style guide bans', () => {
    const text = JSON.stringify(explainers).toLowerCase();
    for (const banned of ['residual', 'regression', 'percentile', 'confidence interval', 'deff']) {
      expect(text).not.toContain(banned);
    }
  });

  it('says fullscreen and the CSV cover every Sunday with weather on the per-Sunday charts', () => {
    expect(explainers['wf']?.computed.join(' ')).toContain(
      'fullscreen and the CSV download show every Sunday with weather',
    );
    for (const key of ['wr', 'wb', 'wt']) {
      expect(explainers[key]?.computed.join(' ')).toContain(
        'Fullscreen and the CSV download use every Sunday with weather on record.',
      );
    }
  });

  it('says fullscreen draws every shooter on the sensitivity chart', () => {
    expect(explainers['ws']?.read?.join(' ')).toContain(
      'Only the 12 biggest effects are drawn here; fullscreen draws everyone, and the table and CSV list everyone.',
    );
  });
});
