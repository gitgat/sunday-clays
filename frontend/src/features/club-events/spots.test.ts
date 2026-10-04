import { describe, expect, it } from 'vitest';
import cases from './admitCases.json';
import { wouldWaitlist } from './spots';

describe('wouldWaitlist mirrors the server admit rule (shared table, §7.3)', () => {
  it.each(cases)('$case', (c) => {
    const event = { capacity: c.capacity, spots_taken: c.going_spots, waitlist_count: c.waitlist };
    expect(wouldWaitlist(event, c.new_spots)).toBe(c.expect === 'waitlist');
  });
});
