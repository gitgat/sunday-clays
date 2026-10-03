import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { cacheStatusText, changedText, FEATURES_INTRO, INFRA_INTRO } from './copy';
import { featureSwitches, pageCacheStatus } from './mocks';

describe('Features page copy', () => {
  it('formats the change date and the never-changed case', () => {
    expect(changedText('2026-10-02')).toBe('Changed Oct 2, 2026');
    expect(changedText(null)).toBe('Never changed');
  });

  it('uses no banned word in the intro, labels and descriptions', () => {
    const texts = [
      FEATURES_INTRO,
      ...allStrings(featureSwitches.map(({ label, description }) => ({ label, description }))),
    ];
    for (const text of texts) expect(text).not.toMatch(BANNED_WORDS);
  });
});

describe('page cache status line', () => {
  it('reports stored pages, size and the last refresh', () => {
    expect(cacheStatusText(pageCacheStatus)).toBe(
      '1,240 pages stored · 38 MB · last refreshed Oct 2, 2026 (27 pages in 41 s)',
    );
  });

  it('says refreshing when the last warm-up is for an older version or date', () => {
    const stale = { ...pageCacheStatus, current: { data_version: 413, local_date: '2026-10-02' } };
    expect(cacheStatusText(stale)).toBe('Refreshing…');
    const tomorrow = {
      ...pageCacheStatus,
      current: { data_version: 412, local_date: '2026-10-03' },
    };
    expect(cacheStatusText(tomorrow)).toBe('Refreshing…');
  });

  it('says never refreshed, off, and forced off', () => {
    expect(cacheStatusText({ ...pageCacheStatus, last_warm: null })).toBe('Not refreshed yet');
    expect(cacheStatusText({ ...pageCacheStatus, enabled: false })).toBe(
      'Off. Pages compute live and nothing is stored.',
    );
    expect(cacheStatusText({ ...pageCacheStatus, enabled: false, forced_off: true })).toBe(
      'Turned off on the server',
    );
  });

  it('uses no banned word', () => {
    const lines = [
      INFRA_INTRO,
      cacheStatusText(pageCacheStatus),
      cacheStatusText({ ...pageCacheStatus, last_warm: null }),
    ];
    for (const text of lines) expect(text).not.toMatch(BANNED_WORDS);
  });
});
