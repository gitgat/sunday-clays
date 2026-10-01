import { http, HttpResponse } from 'msw';
import { insightFixture } from '../insights/mocks';
import type { BumpCounts, SheetIssue, SheetPost } from './api';

/** An insight post about Ike Hadley (shooter 3): a personal best, linking the profile trend chart. */
export function postFixture(overrides: Partial<SheetPost> = {}): SheetPost {
  const insight = insightFixture();
  return {
    post_key: insight.key,
    type: 'milestone',
    family: 'milestone',
    headline: insight.headline,
    named_shooter_ids: [3],
    see_why: { kind: 'chart', label: insight.chart.label, chart: insight.chart, href: null },
    insight,
    trophy: null,
    on_this_day: null,
    ...overrides,
  };
}

export const trophyPost: SheetPost = postFixture({
  post_key: 'trophy:first_win:2026-09-27',
  type: 'trophy',
  family: 'trophy',
  headline: [
    { t: 'trophy', v: 'First win' },
    { t: 'text', v: ' unlocked by ' },
    { t: 'shooter', v: 'Amy Ace', id: 1 },
    { t: 'text', v: ' and ' },
    { t: 'shooter', v: 'Bob Bee', id: 2 },
    { t: 'text', v: '.' },
  ],
  named_shooter_ids: [1, 2],
  see_why: {
    kind: 'link',
    label: 'First win in the Trophy Room',
    chart: null,
    href: '/achievements/first_win',
  },
  insight: null,
  trophy: {
    code: 'first_win',
    title: 'First win',
    art_key: 'first_win',
    metal: null,
    holders: [
      { shooter_id: 1, name: 'Amy Ace' },
      { shooter_id: 2, name: 'Bob Bee' },
    ],
  },
});

export const onThisDayPost: SheetPost = postFixture({
  post_key: 'otd:2026-09-27:1',
  type: 'on_this_day',
  family: 'on_this_day',
  headline: [
    { t: 'text', v: 'One year ago, on ' },
    { t: 'date', v: 'Sep 28, 2025' },
    { t: 'text', v: ', ' },
    { t: 'num', v: '31' },
    { t: 'text', v: ' shooters came out and the top score was ' },
    { t: 'num', v: '48' },
    { t: 'text', v: '.' },
  ],
  named_shooter_ids: [],
  see_why: {
    kind: 'link',
    label: "That Sunday's results",
    chart: null,
    href: '/events/2025-09-28',
  },
  insight: null,
  on_this_day: { years_ago: 1, event_date: '2025-09-28', n_shooters: 31, top_score: 48 },
});

export const streakPost: SheetPost = postFixture({
  post_key: 'k-streak-5',
  type: 'other',
  family: 'streak',
  headline: [
    { t: 'num', v: '6' },
    { t: 'text', v: ' Sundays in a row above ' },
    { t: 'shooter', v: 'Cal Cy', id: 5 },
    { t: 'text', v: "'s own average." },
  ],
  named_shooter_ids: [5],
  insight: insightFixture({ key: 'k-streak-5', kind: 'pf.above-own-avg-streak', subject_id: '5' }),
});

export function sheetFixture(overrides: Partial<SheetIssue> = {}): SheetIssue {
  return {
    data_version: 7,
    masthead: {
      date: '2026-09-27',
      issue: 310,
      previous: '2026-09-13',
      next: null,
      latest: true,
      newer: null,
    },
    numbers: { shooters: 23, median: 39, top_score: 49, trophies: 13 },
    headline: null,
    recap: null,
    spotlight: null,
    posts: [postFixture(), trophyPost, onThisDayPost],
    more: [{ family: 'streak', label: 'Streaks', posts: [streakPost] }],
    ...overrides,
  };
}

export const bumpsFixture: BumpCounts = {
  'k-pb-3': { bumps: 2, bumped: false },
  'trophy:first_win:2026-09-27': { bumps: 5, bumped: true },
  'otd:2026-09-27:1': { bumps: 0, bumped: false },
  'k-streak-5': { bumps: 1, bumped: false },
};

export const handlers = [
  http.get('*/api/sheet/latest', () => HttpResponse.json(sheetFixture())),
  http.get('*/api/sheet/:date/bumps', () => HttpResponse.json(bumpsFixture)),
  http.get('*/api/sheet/:date', () => HttpResponse.json(sheetFixture())),
];
