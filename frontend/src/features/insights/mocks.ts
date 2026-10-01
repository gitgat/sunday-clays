import { http, HttpResponse } from 'msw';
import type { Insight, InsightFeed, InsightKudos } from './api';

/** A third-person insight about shooter 3 with a "you" twin, linking to the profile trend chart. */
export function insightFixture(overrides: Partial<Insight> = {}): Insight {
  return {
    key: 'k-pb-3',
    kind: 'pf.pb',
    family: 'milestone',
    subject_type: 'shooter',
    subject_id: '3',
    anchor_date: '2026-09-27',
    polarity: 'positive',
    kudos: true,
    is_new: false,
    headline: [
      { t: 'text', v: 'New personal best for ' },
      { t: 'shooter', v: 'Ike Hadley', id: 3 },
      { t: 'text', v: ': ' },
      { t: 'num', v: '46' },
      { t: 'text', v: '.' },
    ],
    headline_you: [
      { t: 'text', v: 'New personal best: ' },
      { t: 'num', v: '46' },
      { t: 'text', v: '.' },
    ],
    headline_text: 'New personal best for Ike Hadley: 46.',
    how: [[{ t: 'text', v: 'The best round beats every earlier round.' }]],
    how_you: [[{ t: 'text', v: 'Your best round beats every earlier round of yours.' }]],
    chart: {
      type: 'page',
      label: "Ike Hadley's scores, with the personal-best line",
      label_you: 'Your scores, with the personal-best line',
      spec: null,
      chart_type: null,
      route: '/shooters/3',
      anchor: 'trend',
      params: { line: 'pb' },
      highlight: { dates: ['2026-09-27'] },
      ref: null,
      compare: null,
      window: { from: '2026-06-27', to: '2026-09-27' },
      also: [],
    },
    rank_score: 9,
    ...overrides,
  };
}

export function kudosFixture(n: number): InsightKudos[] {
  return Array.from({ length: n }, (_, i) => ({
    shooter_id: 100 + i,
    display_name: `Shooter${String(i + 1)}, Pat`,
    insight: insightFixture({ key: `k-${String(i)}`, subject_id: String(100 + i) }),
  }));
}

export function feedFixture(overrides: Partial<InsightFeed> = {}): InsightFeed {
  return {
    data_version: 7,
    as_of: '2026-09-27',
    pinned: null,
    hero: null,
    spotlight: null,
    conditions: null,
    top: [],
    kudos: [],
    more: [],
    n_more: 0,
    ...overrides,
  };
}

export const handlers = [
  http.get('*/api/insights/shooters/:id', () =>
    HttpResponse.json(feedFixture({ top: [insightFixture()] })),
  ),
  http.get('*/api/insights/sundays/:date', () => HttpResponse.json(feedFixture())),
  http.get('*/api/insights/club', () => HttpResponse.json(feedFixture())),
  http.get('*/api/insights/leaderboards', () => HttpResponse.json(feedFixture())),
  http.get('*/api/insights/records', () => HttpResponse.json(feedFixture())),
  http.get('*/api/insights/stations', () => HttpResponse.json(feedFixture())),
];
