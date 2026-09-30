import { describe, expect, it } from 'vitest';
import { legacyWindow, sundaysBetween } from './urlState';

describe('sundaysBetween', () => {
  it('counts the Sundays from a date to a date, both inclusive', () => {
    // 2026-08-03 is a Monday; 2026-09-27 is a Sunday: Aug 9, 16, 23, 30, Sep 6, 13, 20, 27.
    expect(sundaysBetween('2026-08-03', '2026-09-27')).toBe(8);
    expect(sundaysBetween('2026-09-27', '2026-09-27')).toBe(1);
    expect(sundaysBetween('2026-09-20', '2026-10-04')).toBe(3);
  });

  it('is zero for a span with no Sunday in it', () => {
    expect(sundaysBetween('2026-09-21', '2026-09-26')).toBe(0);
  });
});

describe('legacyWindow', () => {
  it('turns both dates into a Custom window', () => {
    expect(legacyWindow('2025-01-05', '2025-06-29', null, null)).toBe('2025-01-05..2025-06-29');
  });

  it('borrows a missing end from the first or latest scored Sunday', () => {
    expect(legacyWindow('2025-01-05', null, '2020-01-05', '2026-09-27')).toBe(
      '2025-01-05..2026-09-27',
    );
    expect(legacyWindow(null, '2025-06-29', '2020-01-05', '2026-09-27')).toBe(
      '2020-01-05..2025-06-29',
    );
  });

  it('is null when there is nothing to convert, no scored Sunday to borrow, or a reversed span', () => {
    expect(legacyWindow(null, null, '2020-01-05', '2026-09-27')).toBeNull();
    expect(legacyWindow('2025-01-05', null, null, null)).toBeNull();
    expect(legacyWindow(null, '2025-01-05', undefined, undefined)).toBeNull();
    expect(legacyWindow('2025-06-29', '2025-01-05', null, null)).toBeNull();
  });
});
