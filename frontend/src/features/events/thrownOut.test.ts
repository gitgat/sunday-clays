import { describe, expect, it } from 'vitest';
import { BANNED_WORDS } from '../../test/language';
import { eventSummaries, thrownOutDetail, thrownOutSummary, THROWN_OUT_10 } from './mocks';
import {
  excludedNote,
  SUNDAY_THROWN_OUT,
  THROWN_OUT_RECAP_LINE,
  thrownOutBanner,
  thrownOutPhrase,
  type ThrownOut,
} from './thrownOut';

const st = (station_label: string, target_count: number, credited = true): ThrownOut => ({
  station_label,
  target_count,
  credited,
});
const SUNDAY: ThrownOut = { station_label: null, target_count: null, credited: false };

describe('thrownOutPhrase', () => {
  it.each<[ThrownOut[], string]>([
    [[st('11', 7)], 'Station 11 was thrown out; everyone was credited 7/7'],
    [[st('11', 7, false)], 'Station 11 was thrown out'],
    [[st('4', 7), st('11', 7)], 'Stations 4 and 11 were thrown out; everyone was credited in full'],
    [[st('4', 7, false), st('11', 7)], 'Stations 4 and 11 were thrown out'],
    [[st('3', 7, false), st('4', 7), st('11', 7)], 'Stations 3, 4 and 11 were thrown out'],
    [[SUNDAY], 'A station was thrown out this Sunday'],
    [[st('7A', 6), SUNDAY], 'Station 7A was thrown out; everyone was credited 6/6'],
    [[], 'A station was thrown out this Sunday'],
  ])('thrownOutPhrase(%j) is %s', (items, want) => {
    expect(thrownOutPhrase(items)).toBe(want);
  });

  it('exports the Sunday-level phrase', () => {
    expect(SUNDAY_THROWN_OUT).toBe('A station was thrown out this Sunday');
  });
});

it('builds the Sunday banner from the phrase', () => {
  expect(thrownOutBanner([st('11', 7)])).toBe(
    "Station 11 was thrown out; everyone was credited 7/7. Today's results and standings count, marked *. These scores are left out of averages, PBs and station stats.",
  );
});

it.each([
  [0, null],
  [1, '1 round marked * not in the average'],
  [2, '2 rounds marked * not in the average'],
])('excludedNote(%i)', (n, want) => {
  expect(excludedNote(n)).toBe(want);
});

it('pins the recap line the server sends', () => {
  expect(THROWN_OUT_RECAP_LINE).toBe(
    'A station was thrown out this Sunday. Its results count; its scores stay out of averages and PBs.',
  );
});

it('uses no banned word', () => {
  expect(
    [
      thrownOutPhrase([SUNDAY]),
      thrownOutBanner([st('4', 7), st('11', 7)]),
      excludedNote(2),
      THROWN_OUT_RECAP_LINE,
    ].join(' '),
  ).not.toMatch(BANNED_WORDS);
});

describe('thrown-out mocks', () => {
  it('flag the Sunday, its results and the thrown-out layout row', () => {
    expect(THROWN_OUT_10).toEqual({ station_label: '10', target_count: 8, credited: true });
    expect(thrownOutDetail.event_date).toBe('2026-10-25');
    expect(thrownOutDetail.stats_excluded).toBe(true);
    expect(thrownOutDetail.thrown_out).toEqual([THROWN_OUT_10]);
    expect(thrownOutDetail.vs_prev).toBeNull();
    expect(thrownOutDetail.results.every((r) => r.stats_excluded && r.adjusted === null)).toBe(
      true,
    );
    expect(thrownOutDetail.stations?.layout.filter((s) => s.dropped).map((s) => s.label)).toEqual([
      '10',
    ]);
    expect(thrownOutSummary.stats_excluded).toBe(true);
    expect(thrownOutSummary.thrown_out).toEqual([THROWN_OUT_10]);
    expect(eventSummaries).not.toContain(thrownOutSummary);
  });
});
