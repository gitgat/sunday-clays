import { describe, expect, it } from 'vitest';
import { safeNext } from './safeNext';

describe('safeNext', () => {
  it.each([
    ['an absolute URL to another site', 'https://evil.com'],
    ['a protocol-relative URL', '//evil.com'],
    ['a backslash authority', '/\\evil.com'],
    ['a tab-smuggled authority', '/\t/evil.com'],
    ['?next=/%0a/evil.com as decoded by URLSearchParams', '/\n/evil.com'],
    [
      'the 401 redirect from pathname //evil.com/x (next=%2F%2Fevil.com%2Fx, decoded)',
      '//evil.com/x',
    ],
    ['a javascript: URL', 'javascript:alert(1)'],
    ['a relative path without a leading slash', 'events'],
    ['an empty value', ''],
    ['a smuggled authority the URL parser cannot parse (?next=/%0a/[)', '/\n/['],
    // Dot segments pass the raw-prefix checks but resolve to a protocol-relative '//evil.com'.
    ['a single-dot segment before an authority', '/.//evil.com'],
    ['a double-dot segment before an authority', '/..//evil.com'],
    ['an encoded single-dot segment', '/%2e//evil.com'],
    ['an encoded double-dot segment', '/%2E%2E//evil.com'],
    ['a path walked back to an authority', '/x/..//evil.com'],
    ['a dot segment before a backslash authority', '/./\\evil.com'],
    ['a dot segment with a backslash separator', '/.\\/evil.com'],
  ])('rejects %s', (_label, next) => {
    expect(safeNext(next)).toBe('/');
  });

  it('falls back to / when next is missing', () => {
    expect(safeNext(null)).toBe('/');
  });

  it('keeps a same-origin path with its query and hash', () => {
    expect(safeNext('/events/2026-09-13?x=1')).toBe('/events/2026-09-13?x=1');
    expect(safeNext('/explorer?m=score#chart')).toBe('/explorer?m=score#chart');
  });
});
