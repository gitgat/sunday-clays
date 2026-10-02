import { describe, expect, it } from 'vitest';
import { pageKind } from './pageKind';

describe('pageKind', () => {
  it.each([
    ['/', 'home'],
    ['/shooters/3', 'profile'],
    ['/shooters/3/', 'profile'],
    ['/shooters', 'other'],
    ['/events', 'events-list'],
    ['/events/2026-09-27', 'event'],
    ['/leaderboards', 'leaderboards'],
    ['/records', 'records'],
    ['/club', 'club'],
    ['/stations', 'stations'],
    ['/weather', 'weather'],
    ['/yir', 'yir'],
    ['/yir/2025/shooters/3', 'yir'],
    ['/explorer', 'explorer'],
    ['/achievements/first_25', 'achievements'],
    ['/race', 'race'],
    ['/compare', 'compare'],
    ['/admin/analytics', 'admin'],
    ['/login', 'other'],
    ['/constructor', 'other'],
    ['/no-such-page', 'other'],
  ])('%s is %s', (path, kind) => {
    expect(pageKind(path)).toBe(kind);
  });

  it('never carries an id or a path', () => {
    for (const path of ['/shooters/3', '/events/2026-09-27', '/yir/2025/shooters/3']) {
      expect(pageKind(path)).not.toMatch(/\d|\//);
    }
  });
});
