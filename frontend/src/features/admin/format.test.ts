import { describe, expect, it } from 'vitest';
import { dateList, formatDay, formatTimestamp, kindLabel, statusLabel } from './format';

describe('admin formatting', () => {
  it('formats timestamps in club time', () => {
    expect(formatTimestamp('2026-09-27T18:05:00Z')).toMatch(/^Sep 27, 2026, 11:05\sAM$/);
    expect(formatTimestamp(null)).toBe('—');
  });

  it('formats event dates without timezone drift', () => {
    expect(formatDay('2026-09-06')).toBe('Sep 6, 2026');
  });

  it.each([
    ['pending', 'Pending'],
    ['committed', 'Committed'],
    ['discarded', 'Discarded'],
    ['rolled_back', 'Rolled back'],
    ['odd', 'odd'],
  ])('status %s → %s', (status, want) => {
    expect(statusLabel(status)).toBe(want);
  });

  it.each([
    ['scores', 'Scores workbook'],
    ['stations', 'Station workbook'],
    ['other', 'other'],
  ])('kind %s → %s', (kind, want) => {
    expect(kindLabel(kind)).toBe(want);
  });

  it('lists dates or a dash', () => {
    expect(dateList(['2026-09-06', '2026-09-13'])).toBe('Sep 6, 2026, Sep 13, 2026');
    expect(dateList([])).toBe('—');
  });
});
