import { describe, expect, it } from 'vitest';

import type { HistoryFrame } from './api';
import { bumpTable, frameTable, racerNames, toLeaderboardFrame } from './transforms';

const JAN_11: HistoryFrame = {
  event_date: '2026-01-11',
  rows: [
    { shooter_id: 2, display_name: 'Bee, Bob', status: 'guest', value: 20, rank: 1 },
    { shooter_id: 1, display_name: 'Ace, Amy', status: 'member', value: 20, rank: 1 },
  ],
};

const FRAMES: HistoryFrame[] = [
  {
    event_date: '2026-01-04',
    rows: [
      { shooter_id: 1, display_name: 'Ace, Amy', status: 'member', value: 11, rank: 1 },
      { shooter_id: 2, display_name: 'Bee, Bob', status: 'guest', value: 9, rank: 2 },
    ],
  },
  JAN_11,
];

describe('racerNames', () => {
  it('gives namesakes one #id name in every frame, even frames where only one of them appears', () => {
    const jim = (shooter_id: number, value: number, rank: number) => ({
      shooter_id,
      display_name: 'Desmond',
      status: 'guest' as const,
      value,
      rank,
    });
    const alone: HistoryFrame = { event_date: '2026-01-04', rows: [jim(7, 10, 1)] };
    const both: HistoryFrame = { event_date: '2026-01-11', rows: [jim(7, 18, 1), jim(9, 10, 2)] };
    const names = racerNames([alone, both]);
    expect(names.get(7)).toBe('Desmond #7');
    expect(names.get(9)).toBe('Desmond #9');
    expect(toLeaderboardFrame(alone, names).rows.map((r) => r.name)).toEqual(['Desmond #7']);
    expect(racerNames(FRAMES).get(1)).toBe('Ace, Amy');
  });
});

describe('toLeaderboardFrame', () => {
  it("maps a history frame onto the race/bump builders' LeaderboardFrame, keeping API order and shared ranks", () => {
    expect(toLeaderboardFrame(JAN_11, racerNames(FRAMES))).toEqual({
      date: '2026-01-11',
      rows: [
        { id: 2, name: 'Bee, Bob', value: 20, rank: 1 },
        { id: 1, name: 'Ace, Amy', value: 20, rank: 1 },
      ],
    });
  });

  it('falls back to the display name for a shooter missing from the name map', () => {
    expect(toLeaderboardFrame(JAN_11, new Map()).rows.map((r) => r.name)).toEqual([
      'Bee, Bob',
      'Ace, Amy',
    ]);
  });
});

describe('frameTable', () => {
  it('turns one frame into shooter/value rows in API order', () => {
    expect(frameTable(FRAMES[1], 'Points')).toEqual({
      columns: [
        { key: 'display_name', label: 'Shooter', type: 'string' },
        { key: 'value', label: 'Points', type: 'number' },
      ],
      rows: [
        { display_name: 'Bee, Bob', value: 20, shooter_id: 2 },
        { display_name: 'Ace, Amy', value: 20, shooter_id: 1 },
      ],
    });
  });

  it('is empty without a frame', () => {
    expect(frameTable(undefined, 'Wins').rows).toEqual([]);
  });
});

describe('bumpTable', () => {
  it('lists every frame row with its event date and shared rank', () => {
    expect(bumpTable(FRAMES).rows).toEqual([
      { event_date: '2026-01-04', display_name: 'Ace, Amy', rank: 1 },
      { event_date: '2026-01-04', display_name: 'Bee, Bob', rank: 2 },
      { event_date: '2026-01-11', display_name: 'Bee, Bob', rank: 1 },
      { event_date: '2026-01-11', display_name: 'Ace, Amy', rank: 1 },
    ]);
  });
});

describe('table names', () => {
  const jim = (shooter_id: number, rank: number) => ({
    shooter_id,
    display_name: 'Desmond',
    status: 'guest' as const,
    value: 10,
    rank,
  });
  const frame: HistoryFrame = { event_date: '2026-01-11', rows: [jim(7, 1), jim(9, 2)] };
  const names = racerNames([frame]);

  it('frameTable uses the race-wide names so namesakes are distinguishable', () => {
    expect(frameTable(frame, 'Wins', names).rows.map((r) => r.display_name)).toEqual([
      'Desmond #7',
      'Desmond #9',
    ]);
  });

  it('bumpTable uses the race-wide names so namesakes are distinguishable', () => {
    expect(bumpTable([frame], names).rows.map((r) => r.display_name)).toEqual([
      'Desmond #7',
      'Desmond #9',
    ]);
  });
});
